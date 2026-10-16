# Astra – Teacher → Student Android Vuln Scanner

Static scan of a decompiled Android app with a frontier model (teacher), the same scan with a
small open model (student), then teacher-written **general lessons** to improve the student.
We measure the student's recall before and after.

## Flow

```
APK ─► ingest ─► App ─► scan(teacher) ─► findings ─► lessons ─┐
                   └──► scan(student)            ─► before    │
                   └──► scan(student + lessons)  ─► after  ◄──┘
                                    match(findings, ground truth) ─► recall / precision
```

## Layout

| Path | What it does |
|---|---|
| `config.yaml` | App path, models, thresholds, vulnerability categories. **Nothing app-specific in code.** |
| `astra/schemas.py` | Data shapes: `App`, `Component`, `Finding`, `GroundTruth` |
| `astra/llm.py` | Model layer. Any OpenAI-compatible API; adding a model = config entry |
| `astra/ingest.py` | Decompile APK (jadx + apktool), parse manifest, drop library code |
| `astra/scan.py` | Chunk code, ask model for JSON findings, verify evidence, dedupe |
| `astra/lessons.py` | Teacher findings → general rules; filter out app-specific ones |
| `astra/match.py` | Match findings to ground truth, compute recall / precision |
| `astra/loop.py` | Runs the full teacher → student experiment |
| `prompts/` | Prompt text, kept out of code |
| `groundtruth/` | Labelled vulns per app (YAML). A new app = a new file |
| `apks/`, `runs/` | Inputs and outputs (gitignored) |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add your keys
# external tools: Java 11+, jadx, apktool on PATH
```

## Run

```bash
python main.py ingest
python main.py scan --model teacher
python main.py loop
python main.py loop --apk apks/other.apk    # a different app
```
