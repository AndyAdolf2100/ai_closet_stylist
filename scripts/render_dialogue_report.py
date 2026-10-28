"""Render a self-contained HTML report from synthetic dialogue test evidence."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def render(inputs, annotations, output):
    records, batches = [], []
    for path in inputs:
        batch = json.loads(Path(path).read_text())
        if batch.get("kind") != "live_text_model_synthetic_adapters":
            raise ValueError("Only synthetic-adapter dialogue reports may be exported")
        batches.append({"file": Path(path).name, "model": batch["model"], "total": batch["total"],
                       "review_prompt": batch.get("review_prompt", "review_dialogue"),
                       "profile_sha256": batch.get("profile_sha256", {})})
        records.extend(batch["cases"])
    manual = json.loads(Path(annotations).read_text()) if annotations else {"issues": [], "cases": {}}
    if len({row["case"] for row in records}) != len(records):
        raise ValueError("Duplicate cases: do not combine a raw batch and its re-review")
    data = {"generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M 上海时间"),
            "batches": batches, "records": records, "manual": manual}
    template = Path(__file__).with_name("report_assets").joinpath("dialogue_report.html").read_text()
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    result = template.replace("__REPORT_DATA__", payload)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--annotations")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = render(args.input, args.annotations, args.output)
    print(json.dumps({"rounds": len(data["records"]), "output": args.output}, ensure_ascii=False))
