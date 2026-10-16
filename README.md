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
| `astra/ingest.py` | Decompile APK with jadx, parse manifest, keep app code, list libraries |
| `astra/chunker.py` | Split the app into pieces that fit one model request |
| `astra/scan.py` | Ask model for JSON findings per chunk, verify evidence is real, dedupe |
| `astra/lessons.py` | Teacher findings → general rules; filter out app-specific ones |
| `astra/match.py` | Match findings to ground truth, compute recall / precision |
| `astra/loop.py` | Runs the full teacher → student experiment |
| `prompts/` | Prompt text, kept out of code |
| `groundtruth/` | Labelled vulns per app (YAML). A new app = a new file |
| `apks/`, `runs/` | Inputs and outputs (gitignored) |

## Setup

```bash
./setup.sh                      # venv + deps, local Java + jadx in tools/, sample APK, .env
source .venv/bin/activate
# then add your API keys to .env
```

## Run

```bash
python main.py ingest                      # decompile + summary (exported components, files, libraries)
python main.py chunks --model student      # how the app is split for that model
python main.py scan --model teacher        # findings -> runs/<timestamp>/findings_teacher.json
python main.py loop                        # (todo) teacher -> student experiment
python main.py scan --app apks/other.apk   # a different app (.apk or decompiled folder)
```
