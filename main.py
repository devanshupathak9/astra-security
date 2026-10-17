"""CLI entry point.

  python main.py ingest                         # decompile + load, print a summary
  python main.py chunks --model student         # show how the app is split for that model
  python main.py scan --model teacher           # scan, save findings, score vs ground truth
  python main.py eval runs/<ts>/findings_teacher.json   # re-score a saved findings file
  python main.py loop                           # teacher -> lessons -> student before/after
  python main.py loop --teacher-findings runs/<ts>/findings_teacher_slices.json   # reuse a teacher scan

  --app path/to/other.apk   a different app (an .apk or a decompiled folder)
  --strategy slices         how code is passed: packed | per_file | slices
"""
import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from astra.chunker import STRATEGIES, make_chunks
from astra.config import load_config
from astra.ingest import load_app, summary
from astra.llm import get_llm
from astra.loop import run_loop
from astra.match import load_groundtruth, report
from astra.scan import scan
from astra.schemas import Finding


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "chunks", "scan", "eval", "loop"])
    parser.add_argument("findings", nargs="?", help="findings JSON file (for eval)")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model", default="teacher", help="key under `models` in config")
    parser.add_argument("--app", help="override app.path (an .apk or decompiled folder)")
    parser.add_argument("--strategy", choices=STRATEGIES, help="override scan.strategy")
    parser.add_argument("--teacher-findings", help="loop: reuse a saved teacher findings file")
    args = parser.parse_args()

    config = load_config(args.config)
    strategy = args.strategy or config["scan"]["strategy"]
    depth = config["scan"]["slice_depth"]
    gt_path = config["app"].get("groundtruth")
    labels = load_groundtruth(gt_path) if gt_path and Path(gt_path).exists() else None

    if args.command == "eval":
        print(report(load_findings(args.findings), labels) if labels else "No ground truth configured.")
        return

    app = load_app(args.app or config["app"]["path"], config)

    if args.command == "ingest":
        print(summary(app))

    elif args.command == "chunks":
        max_chars = config["models"][args.model]["max_chunk_chars"]
        for c in make_chunks(app, max_chars, strategy, depth):
            print(f"chunk {c.id}: {len(c.text):,} chars  {[Path(f).name for f in c.files]}")

    elif args.command == "scan":
        model_name = config["models"][args.model]["model"]
        print(f"Scanning {app.package} with {args.model} ({model_name}), strategy={strategy}")
        findings = scan(app, get_llm(config, args.model), config["categories"], strategy, depth,
                        drop_unverified=config["scan"]["drop_unverified"])

        path = new_run_dir(config) / f"findings_{args.model}_{strategy}.json"
        path.write_text(json.dumps([asdict(f) for f in findings], indent=2))
        for f in findings:
            print(f"  [{f.severity:8}] {f.category:28} {Path(f.file).name}:{f.line}  {f.title}")
        print(f"Saved to {path}")
        if labels:
            print("\n" + report(findings, labels))

    elif args.command == "loop":
        out = new_run_dir(config)
        saved = load_findings(args.teacher_findings) if args.teacher_findings else None
        print(run_loop(app, config, labels, strategy, depth, out, saved))
        print(f"\nAll outputs saved in {out}/")


def new_run_dir(config: dict) -> Path:
    out = Path(config["output_dir"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    return out


def load_findings(path: str) -> list[Finding]:
    return [Finding(**f) for f in json.loads(Path(path).read_text())]


if __name__ == "__main__":
    main()
