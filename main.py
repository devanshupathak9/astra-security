"""CLI entry point.

  python main.py ingest                         # decompile + load, print a summary
  python main.py chunks --model student         # show how the app is split for that model
  python main.py scan --model teacher           # scan, save findings, score vs ground truth
  python main.py eval runs/<ts>/findings_teacher.json   # re-score a saved findings file
  python main.py loop                           # teacher -> lessons -> student before/after
  python main.py loop --teacher-findings runs/<ts>/findings_teacher_slices.json   # reuse a teacher scan

  Step by step (same experiment as `loop`, one command per step):
  python main.py scan --model teacher                          # 1. teacher findings
  python main.py scan --model student                          # 2. student alone
  python main.py lessons runs/<ts>/findings_teacher_slices.json   # 3. teacher findings -> lessons.json
  python main.py scan --model student --lessons runs/<ts>/lessons.json   # 4. student with lessons
  python main.py eval <step 2 file> <step 4 file>              # compare before vs after

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
from astra.lessons import make_lessons, split_leaky
from astra.llm import get_llm
from astra.loop import run_loop
from astra.match import load_groundtruth, report, score
from astra.scan import scan
from astra.schemas import Finding


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "chunks", "scan", "lessons", "eval", "loop"])
    parser.add_argument("findings", nargs="*", help="findings JSON file(s), for lessons / eval")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model", default="teacher", help="key under `models` in config")
    parser.add_argument("--app", help="override app.path (an .apk or decompiled folder)")
    parser.add_argument("--strategy", choices=STRATEGIES, help="override scan.strategy")
    parser.add_argument("--teacher-findings", help="loop: reuse a saved teacher findings file")
    parser.add_argument("--lessons", help="scan: add the lessons from this lessons.json to the prompt")
    args = parser.parse_args()

    config = load_config(args.config)
    strategy = args.strategy or config["scan"]["strategy"]
    depth = config["scan"]["slice_depth"]
    gt_path = config["app"].get("groundtruth")
    labels = load_groundtruth(gt_path) if gt_path and Path(gt_path).exists() else None

    if args.command == "eval":
        if not labels:
            print("No ground truth configured.")
            return
        for path in args.findings:
            print(f"\n== {path}\n{report(load_findings(path), labels)}")
        if len(args.findings) > 1:
            print(compare(args.findings, labels))
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
        lessons = json.loads(Path(args.lessons).read_text())["lessons"] if args.lessons else None
        print(f"Scanning {app.package} with {args.model} ({model_name}), strategy={strategy}"
              + (f", with {len(lessons)} lessons" if lessons else ""))
        findings = scan(app, get_llm(config, args.model), config["categories"], strategy, depth,
                        lessons, drop_unverified=config["scan"]["drop_unverified"])

        suffix = "_lessons" if lessons else ""
        path = new_run_dir(config) / f"findings_{args.model}_{strategy}{suffix}.json"
        path.write_text(json.dumps([asdict(f) for f in findings], indent=2))
        for f in findings:
            print(f"  [{f.severity:8}] {f.category:28} {Path(f.file).name}:{f.line}  {f.title}")
        print(f"Saved to {path}")
        if labels:
            print("\n" + report(findings, labels))

    elif args.command == "lessons":
        if len(args.findings) != 1:
            parser.error("lessons takes one teacher findings file")
        teacher = get_llm(config, args.model)
        print(f"Writing lessons from {args.findings[0]} with {args.model} ({teacher.model})")
        lessons = make_lessons(load_findings(args.findings[0]), teacher, config["loop"]["max_lessons"])
        lessons, rejected = split_leaky(lessons, app)
        path = Path(args.findings[0]).parent / "lessons.json"
        path.write_text(json.dumps({"lessons": lessons, "rejected_as_app_specific": rejected}, indent=2))
        for l in lessons:
            print(f"  - {l}")
        for r in rejected:
            print(f"  REJECTED (mentions {', '.join(r['mentions'])}): {r['lesson']}")
        print(f"Saved to {path}")

    elif args.command == "loop":
        out = new_run_dir(config)
        saved = load_findings(args.teacher_findings) if args.teacher_findings else None
        print(run_loop(app, config, labels, strategy, depth, out, saved))
        print(f"\nAll outputs saved in {out}/")


def compare(paths: list[str], labels) -> str:
    lines = ["\n== Comparison", f"  {'file':60} {'strict':>8} {'lenient':>8} {'findings':>9}"]
    for path in paths:
        findings = load_findings(path)
        strict, lenient = score(findings, labels, True), score(findings, labels, False)
        lines.append(f"  {path[-60:]:60} {strict['recall']:>8.0%} {lenient['recall']:>8.0%} {len(findings):>9}")
    return "\n".join(lines)


def new_run_dir(config: dict) -> Path:
    out = Path(config["output_dir"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    return out


def load_findings(path: str) -> list[Finding]:
    return [Finding(**f) for f in json.loads(Path(path).read_text())]


if __name__ == "__main__":
    main()
