"""CLI entry point.

  python main.py ingest            # decompile + parse, print a summary
  python main.py scan --model teacher
  python main.py loop              # full teacher -> student experiment
"""
import argparse

from astra.config import load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "scan", "loop"])
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model", default="teacher", help="key under `models` in config")
    parser.add_argument("--apk", help="override app.apk_path")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.apk:
        config["app"]["apk_path"] = args.apk

    raise NotImplementedError(args.command)


if __name__ == "__main__":
    main()
