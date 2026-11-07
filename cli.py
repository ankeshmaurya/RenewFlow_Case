
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app import exports
from app.engine.pipeline import run_pipeline
from app.llm.messages import build_messages
from app.loader import LoadError, load_folder
from app.settings import Settings


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Reconcile renewals and write auto-approved rows, exceptions and drafted messages.")
    p.add_argument("--data", default="data/sample", help="Folder with the 5 CSV files")
    p.add_argument("--out", default="results", help="Output folder")
    p.add_argument("--as-of", default=None, help="Reference time, ISO format with offset (default from settings)")
    p.add_argument("--policy", choices=["HOLD", "PROVISIONAL_PRO_RATA"], default="HOLD", help="Partial payment policy")
    p.add_argument("--threshold", type=float, default=12.0, help="Stuck threshold in hours")
    args = p.parse_args(argv)

    try:
        tables, _report = load_folder(args.data)
    except LoadError as e:
        print("Could not load data:", e.report.get("message"), file=sys.stderr)
        return 2
    settings = Settings(partial_payment_policy=args.policy, stuck_threshold_hours=args.threshold, use_llm=False)
    if args.as_of:
        settings.as_of = args.as_of
    run = run_pipeline(tables, settings)
    cases = run["cases"]
    messages = asyncio.run(build_messages(cases, "English", False))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = dict(as_of=run["as_of"], generated_at=run["generated_at"], settings=run["settings"], metrics=run["metrics"],
                   orphan_forms=run["orphan_forms"], cases=[c.model_dump(mode="json") for c in cases])
    (out / "full-results.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (out / "auto-approved.csv").write_text(exports.auto_approved_csv(cases), encoding="utf-8")
    (out / "exceptions.csv").write_text(exports.exceptions_csv(cases), encoding="utf-8")
    (out / "messages.json").write_text(json.dumps(messages, indent=2), encoding="utf-8")

    dc = run["metrics"]["decision_counts"]
    print(f"As of {run['as_of']}: {len(cases)} invoices")
    for k, v in dc.items():
        print(f"  {k:28s} {v}")
    print(f"  touchless rate {run['metrics']['touchless_rate_percent']}%, paid but unscheduled Rs {run['metrics']['paid_unscheduled_value_inr']:,.0f}")
    for c in cases:
        print(f"  {c.invoice.id}  {c.decision.value:26s} {c.owner.value:16s} {','.join(c.reason_codes)}")
    print(f"Wrote 4 files to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
