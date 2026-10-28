"""Explicit paid review of saved synthetic dialogues with structured page regions."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from stylist.config import Settings
from stylist.llm import LanguageModel
from stylist.models import Reply
from stylist.personas import persona_instructions

from .dialogue_validation import PersonaReview, review_status, visible_text


async def run(args):
    settings = Settings.load()
    if not (settings.llm_key and settings.llm_url and settings.llm_model):
        raise SystemExit("Live model is not configured")
    source = json.loads(Path(args.input).read_text())
    if source.get("kind") != "live_text_model_synthetic_adapters":
        raise SystemExit("Expected a synthetic-adapter live dialogue report")
    for persona, digest in source.get("profile_sha256", {}).items():
        if hashlib.sha256(persona_instructions(persona).encode()).hexdigest() != digest:
            raise SystemExit("Persona changed since the tested batch; preserve the tested profile before reviewing")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {**source, "initial_summary": {k: source.get(k) for k in [
        "automatic_passed", "accepted", "persona_review_passed", "persona_review_failed", "persona_review_pending"]},
        "review_prompt": "review_dialogue_audit", "review_prompt_sha256": hashlib.sha256(
            Path("stylist/prompts/review_dialogue_audit.md").read_bytes()).hexdigest(), "cases": []}
    histories, jobs = {}, []
    for index, row in enumerate(source["cases"]):
        prefix, group, _ = row["case"].split("/", 2)
        key = (prefix, group)
        previous = histories.get(key) if group != "single" else None
        if row.get("reply"):
            histories[key] = row["reply"]
        jobs.append((index, row, previous))
    semaphore = asyncio.Semaphore(args.concurrency)

    def save():
        rows = report["cases"]
        report.update(total=len(rows), automatic_passed=sum(not row["automatic_errors"] for row in rows),
            persona_review_passed=sum(row["persona_review"]["status"] == "passed" for row in rows),
            persona_review_failed=sum(row["persona_review"]["status"] in {"failed", "invalid_evidence", "error"} for row in rows),
            persona_review_pending=sum(row["persona_review"]["status"] == "pending" for row in rows),
            accepted=sum(not row["errors"] and row["persona_review"]["status"] == "passed" for row in rows))
        temp = output.with_suffix(output.suffix + ".tmp")
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        os.replace(temp, output)

    async def one(index, row, previous):
        async with semaphore:
            item = {**row, "source_index": index, "initial_persona_review": row["persona_review"],
                    "errors": row["automatic_errors"].copy()}
            if not row.get("reply"):
                item["persona_review"] = {"status": "not_reviewable"}
            else:
                reply = Reply.model_validate(row["reply"])
                try:
                    review = await LanguageModel(settings).generate("review_dialogue_audit", {
                        "expected_persona": persona_instructions(row["persona"]), "message": row["message"],
                        "reply_parts": {k: row["reply"].get(k) for k in ["message", "looks", "warnings", "follow_ups"]},
                        "visible_reply": visible_text(reply), "previous_reply": previous,
                        "current_weather": reply.weather, "current_items": [p.model_dump(mode="json") for look in reply.looks for p in look.items],
                        "current_task": reply.task.model_dump(mode="json"), "expected": row.get("expected", {}),
                        "business_events": row.get("business_events", []), "business_calls": row.get("business_calls", []),
                    }, PersonaReview)
                    status = review_status(review, visible_text(reply))
                    item["persona_review"] = {**review.model_dump(), "status": status, "reviewer_model": settings.llm_model}
                    if status != "passed":
                        item["errors"].append("persona_review_" + status)
                except Exception as exc:
                    item["persona_review"] = {"status": "error", "code": getattr(exc, "code", type(exc).__name__)}
                    item["errors"].append("persona_review_error")
            report["cases"].append(item)
            report["cases"].sort(key=lambda row: row["source_index"])
            save()
            print(json.dumps({"case": row["case"], "review": item["persona_review"]["status"]}), flush=True)

    await asyncio.gather(*(one(*job) for job in jobs))
    return 1 if any(row["errors"] for row in report["cases"]) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--concurrency", type=int, default=4)
    options = parser.parse_args()
    if not 1 <= options.concurrency <= 8:
        parser.error("concurrency must be between 1 and 8")
    raise SystemExit(asyncio.run(run(options)))
