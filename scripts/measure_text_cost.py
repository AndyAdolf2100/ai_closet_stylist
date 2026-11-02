"""Opt-in paid text measurement with synthetic wardrobe and isolated storage.

Capture provider usage for every attempt (including repair), never keys or headers.
Run: STYLIST_LEGACY_CONFIG=../ai_closet_agent/config/config.yaml \
  .venv/bin/python -m scripts.measure_text_cost --live
"""
import argparse
import asyncio
import json
import tempfile
import time
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from scripts.dialogue_validation import DialogueUpstream
from scripts.preference_dialogues import PRODUCTS
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.llm import LanguageModel
from stylist.models import ChatRequest
from stylist.store import Store


def accounting(row):
    """Input includes cached tokens; charge each input token only once."""
    if not row["calls"] or any(not c.get("usage") for c in row["calls"]):
        return None
    usage = [c["usage"] for c in row["calls"]]
    prompt = sum(u["prompt_tokens"] for u in usage)
    completion = sum(u["completion_tokens"] for u in usage)
    cached = sum(u.get("prompt_tokens_details", {}).get("cached_tokens", 0) for u in usage)
    assert 0 <= cached <= prompt
    assert all(u["total_tokens"] == u["prompt_tokens"] + u["completion_tokens"] for u in usage)
    return {"input": prompt, "output": completion, "cached": cached,
            "listed_cny": str((Decimal(prompt - cached) * 6 + Decimal(cached) * Decimal("1.2")
                               + Decimal(completion) * 30) / 1_000_000),
            "no_cache_cny": str(Decimal(prompt * 6 + completion * 30) / 1_000_000)}


class Meter(httpx.AsyncBaseTransport):
    def __init__(self):
        self.inner = httpx.AsyncHTTPTransport()
        self.stage = None
        self.calls = []

    async def handle_async_request(self, request):
        start = time.monotonic()
        body = json.loads(request.content)
        try:
            response = await self.inner.handle_async_request(request)
            await response.aread()
        except httpx.HTTPError as exc:
            self.calls.append({"stage": self.stage, "error": type(exc).__name__, "usage": None})
            raise
        row = {"stage": self.stage, "http_status": response.status_code,
               "seconds": round(time.monotonic() - start, 3),
               "input_characters": sum(len(m["content"]) for m in body["messages"])}
        if response.is_success:
            data = response.json()
            row.update(model=data.get("model"), usage=data.get("usage"),
                       finish_reason=data["choices"][0].get("finish_reason"))
        self.calls.append(row)
        return response


class Observed(LanguageModel):
    async def generate(self, name, payload, result_type):
        self.transport.stage = name
        return await super().generate(name, payload, result_type)


async def run(args):
    settings = Settings.load()
    cases = [] if args.outfits_only else [("chat", "今天工作有点累，陪我聊两句。", None)]
    for n in args.counts:
        cases.append((f"day_{n}", f"我是女生，请从我的衣橱给我今天的{n}套日常通勤穿搭，明确分成{n}套，每套有选款理由和穿法。上海今天晴，15到20度，按这个天气，不用另外查天气。", n))
    if not args.outfits_only:
        cases.append(("week_7", "我是女生，请从我的衣橱安排本周周一到周日的穿搭，每天一套，共7套，分别标明日期、选款理由和穿法。不考虑天气。", 7))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "kind": "live_text_synthetic_business", "requested_model": settings.llm_model,
              "wardrobe_count": len(PRODUCTS), "repeats": args.repeats,
              "counts": args.counts, "concurrency": args.concurrency, "cases": []}
    semaphore = asyncio.Semaphore(args.concurrency)

    async def measure(label, message, expected, repeat):
        async with semaphore:
            meter = Meter()
            row = {"case": label, "repeat": repeat, "message": message, "expected_looks": expected}
            with tempfile.TemporaryDirectory(prefix="stylist-cost-") as temp:
                local = replace(settings, database=str(Path(temp) / "state.db"), checkpoint_database="")
                upstream = DialogueUpstream("cost_measurement")
                upstream.products = PRODUCTS
                try:
                    reply = await Stylist(local, Store(local.database), Observed(local, meter)).chat(
                        upstream, ChatRequest(message=message, request_id=f"cost-{label}-{repeat}",
                                              assistant_persona="female_warm_v1"))
                    row.update(actual_looks=len(reply.looks), reply=reply.model_dump(mode="json"),
                               expected_count_met=(len(reply.looks) == (expected or 0)))
                except Exception as exc:
                    row["error"] = getattr(exc, "code", type(exc).__name__)
                finally:
                    await meter.inner.aclose()
                row.update(calls=meter.calls, business_calls=upstream.calls)
                report["cases"].append(row)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(json.dumps({k: v for k, v in row.items() if k not in {"reply", "message"}}, ensure_ascii=False), flush=True)

    await asyncio.gather(*(measure(*case, repeat) for repeat in range(1, args.repeats + 1) for case in cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="explicitly allow paid text calls")
    parser.add_argument("--repeats", type=int, choices=range(1, 21), default=2)
    parser.add_argument("--counts", type=int, choices=range(1, 8), nargs="+", default=[1, 2, 3, 5, 7])
    parser.add_argument("--outfits-only", action="store_true", help="omit chat and weekly controls")
    parser.add_argument("--concurrency", type=int, choices=range(1, 9), default=2)
    parser.add_argument("--output", default="var/text-cost/measurement.json")
    parser.add_argument("--report-only", action="store_true", help="summarize an existing report, no model calls")
    args = parser.parse_args()
    if args.report_only:
        report = json.loads(Path(args.output).read_text())
        for row in report["cases"]:
            print(json.dumps({"case": row["case"], "repeat": row["repeat"],
                              "actual_looks": row.get("actual_looks"), "error": row.get("error"),
                              "accounting": accounting(row)}, ensure_ascii=False))
        return
    if not args.live:
        parser.error("--live is required; this invokes the real paid text model")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
