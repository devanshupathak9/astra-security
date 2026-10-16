"""CLI entry point.

  python main.py ingest                    # decompile + load, print a summary
  python main.py chunks --model student    # show how the app is split for that model
  python main.py scan --model teacher      # scan, save findings to runs/
  python main.py loop                      # full teacher -> student experiment (todo)

  --app path/to/other.apk   runs on a different app (an .apk or a decompiled folder)
"""
import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from astra.chunker import make_chunks
from astra.config import load_config
from astra.ingest import load_app, summary
from astra.llm import get_llm
from astra.scan import scan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "chunks", "scan", "loop"])
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model", default="teacher", help="key under `models` in config")
    parser.add_argument("--app", help="override app.path (an .apk or decompiled folder)")
    args = parser.parse_args()

    config = load_config(args.config)
    app = load_app(args.app or config["app"]["path"], config)

    if args.command == "ingest":
        print(summary(app))

    elif args.command == "chunks":
        max_chars = config["models"][args.model]["max_chunk_chars"]
        for c in make_chunks(app, max_chars):
            print(f"chunk {c.id}: {len(c.text):,} chars  {c.files}")

    elif args.command == "scan":
        print(f"Scanning {app.package} with {args.model} ({config['models'][args.model]['model']})")
        findings = scan(app, get_llm(config, args.model), config["categories"],
                        drop_unverified=config["scan"]["drop_unverified"])
        out = Path(config["output_dir"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"findings_{args.model}.json"
        path.write_text(json.dumps([asdict(f) for f in findings], indent=2))
        for f in findings:
            print(f"  [{f.severity:8}] {f.category:28} {f.file}:{f.line}  {f.title}")
        print(f"Saved to {path}")

    else:
        raise NotImplementedError("loop: next step")


if __name__ == "__main__":
    main()
