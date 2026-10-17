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
python main.py ingest                         # decompile + summary (exported components, files, libraries)
python main.py chunks --strategy slices       # how the app is split into requests
python main.py scan --model teacher           # findings -> runs/<ts>/, scored vs ground truth
python main.py scan --model student           # same scan with the open model
python main.py eval runs/<ts>/findings_*.json # re-score a saved findings file
python main.py loop                           # teacher -> lessons -> student before/after
python main.py loop --teacher-findings runs/<ts>/findings_teacher_slices.json   # reuse a teacher scan
python main.py scan --app apks/other.apk      # a different app (.apk or decompiled folder)
```

`--strategy packed | per_file | slices` changes how code is passed to the model (see `config.yaml`).

## Teacher -> student loop

1. Teacher scans the app.
2. Teacher turns its findings into general lessons in one call; lessons naming anything
   from the app (class names, package, custom actions) are rejected.
3. For each student in `loop.students` (two open models from different families by default):
   N scans without lessons -> recall **before**, N scans with the lessons -> recall **after**.
4. `runs/<ts>/report.md`: before vs after per student (mean ± std), per-bug hit counts.

Without a ground-truth file, the teacher's findings are used as labels.
