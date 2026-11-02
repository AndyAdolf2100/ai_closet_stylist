"""Read-only counts for synthetic-adapter live dialogue evidence; no API calls."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def summarize(batch):
    if batch.get("kind") != "live_text_model_synthetic_adapters":
        raise ValueError("Expected synthetic-adapter live dialogue evidence")
    rows = batch["cases"]
    if len({row["case"] for row in rows}) != len(rows):
        raise ValueError("Duplicate cases; do not combine a batch and its re-review")

    def counts(items):
        statuses = Counter(row["persona_review"]["status"] for row in items)
        return {
            "total": len(items),
            "with_reply": sum(bool(row.get("reply")) for row in items),
            "without_reply": sum(not row.get("reply") for row in items),
            "automatic_passed": sum(not row["automatic_errors"] for row in items),
            "review_status": dict(sorted(statuses.items())),
            "accepted": sum(not row["errors"] and row["persona_review"]["status"] == "passed"
                            for row in items),
            "automatic_errors": dict(sorted(Counter(error for row in items
                                                    for error in set(row["automatic_errors"])).items())),
        }

    starting, actual = defaultdict(list), defaultdict(list)
    for row in rows:
        starting[row["case"].split("/", 1)[0]].append(row)
        actual[row["persona"]].append(row)
    result = {
        "model": batch.get("model"),
        "evidence": "live_text_with_synthetic_business_only",
        "counts": counts(rows),
        "by_starting_persona": {key: counts(value) for key, value in sorted(starting.items())},
        "by_actual_persona": {key: counts(value) for key, value in sorted(actual.items())},
        "switch_rounds": sum(row["case"].split("/", 1)[0] != row["persona"] for row in rows),
        "preference_comparison_status": dict(sorted(Counter(
            row["status"] for row in batch.get("preference_comparisons", [])).items())),
        "saved_reply_rereviews": sum("initial_persona_review" in row and bool(row.get("reply")) for row in rows),
        "reused_first_reviews": sum(bool(row.get("review_reused")) for row in rows),
    }
    reported = batch.get("total")
    if reported is not None and reported != len(rows):
        result["reported_total_mismatch"] = reported
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.report.read_text())), ensure_ascii=False, indent=2))
