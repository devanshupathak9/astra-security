# Astra – Teacher → Student Android Vuln Scanner

Static scan of a decompiled Android app with a frontier model (teacher), the same scan with a
small open model (student), then teacher-written **general lessons** to improve the student.
We measure the student's recall before and after.

**Docs:** [`docs/writeup.md`](docs/writeup.md) (write-up) · [`docs/results.md`](docs/results.md)
(recall before / after) · [`docs/architecture.md`](docs/architecture.md) ·
[`docs/problem_statement.md`](docs/problem_statement.md)

## Quick start (3 steps)

**1. Setup** (one time; installs Python deps, Java + jadx locally, downloads InsecureShop, creates `.env`)
```bash
./setup.sh
```

**2. Choose models in `.env`** (copy from `.env.example`). Tested setup:
```bash
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
TEACHER_MODEL=gpt-6.1-sol
STUDENT_MODEL=openai/gpt-oss-20b
STUDENT_BASE_URL=https://api.groq.com/openai/v1
STUDENT_API_KEY_ENV=GROQ_API_KEY
```
Each name must appear only once. `python main.py models --model teacher` lists the model ids your key can use.

**3. Run everything**
```bash
./run_all.sh
```
Teacher scan → lessons → student before / placebo / after → report.
Result: `runs/<time>/report.md` (for InsecureShop also copied to `docs/results.md`).
Takes ~30 min with a student on Groq's free tier (rate limits); `./run_all.sh --free` runs
teacher and student on Groq only (needs just `GROQ_API_KEY`).

## Run on your own APK

```bash
./run_all.sh --app path/to/your.apk                               # an .apk or a decompiled folder
./run_all.sh --app path/to/your.apk --groundtruth your_bugs.yaml  # score against your answer key
```
- Without `--groundtruth`, the **teacher's findings are the answer key**: the report shows how
  close the student gets to the teacher, before and after the lessons.
- An answer key is a YAML list like `groundtruth/insecureshop.yaml`
  (`id`, `title`, `categories` from `config.yaml`, `files` where the bug lives).
- Nothing app-specific is in the code: the app's package, components and code are read from its manifest.

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
| `astra/llm.py` | Model layer: `LLM` interface + one class per provider (OpenAI-compatible, Anthropic). Adding a model = config entry |
| `astra/ingest.py` | Decompile APK with jadx, parse manifest, keep app code, list libraries |
| `astra/chunker.py` | Split the app into pieces that fit one model request |
| `astra/scan.py` | Ask model for JSON findings per chunk, verify evidence is real, dedupe |
| `astra/lessons.py` | Teacher findings → general rules; filter out app-specific ones |
| `astra/match.py` | Match findings to ground truth, compute recall / precision |
| `astra/loop.py` | Runs the full teacher → student experiment |
| `prompts/` | Prompt text, kept out of code |
| `groundtruth/` | Labelled vulns per app (YAML). A new app = a new file |
| `docs/` | Write-up, results, architecture, problem statement |
| `run_all.sh` | Runs the whole experiment with one command |
| `apks/`, `runs/` | Inputs and outputs (gitignored) |

## Setup

```bash
./setup.sh                      # venv + deps, local Java + jadx in tools/, sample APK, .env
source .venv/bin/activate
```

Then fill in `.env` (see `.env.example`). Models are chosen there, not in code:

```bash
OPENAI_API_KEY=sk-...
TEACHER_MODEL=<frontier model id>
STUDENT_MODEL=<small model id>
# Student on Groq instead (open-weight, free tier):
# STUDENT_MODEL=openai/gpt-oss-20b
# STUDENT_BASE_URL=https://api.groq.com/openai/v1
# STUDENT_API_KEY_ENV=GROQ_API_KEY
```

`python main.py models --model teacher` lists the model ids your key can use.

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
python main.py models --model student         # model ids available to that model's key
```

Long runs: `nohup python main.py loop > runs/loop.log 2>&1 &` keeps running after you log out.

`--strategy packed | per_file | slices` changes how code is passed to the model (see `config.yaml`).

## Step by step

The same experiment as `loop`, one command per step, so every intermediate file can be inspected:

```bash
python main.py scan --model teacher                                    # 1. teacher findings
python main.py scan --model student                                    # 2. student alone (before)
python main.py lessons runs/<ts>/findings_teacher_slices.json          # 3. -> runs/<ts>/lessons.json
python main.py scan --model student --lessons runs/<ts>/lessons.json   # 4. student with lessons (after)
python main.py eval <step 2 file> <step 4 file>                        # before vs after
```

## Teacher -> student loop

1. Teacher scans the app.
2. Teacher turns its findings into general lessons in one call; lessons naming anything
   from the app (class names, package, custom actions) are rejected.
3. For each student in `loop.students`, N scans in each condition:
   **before** (no advice), **placebo** (generic advice of the same length, a control) and
   **after** (the lessons). Only the extra prompt text differs between conditions.
4. `runs/<ts>/report.md`: recall per condition (mean ± std), lift vs before and vs placebo,
   per-bug hit counts.

Without a ground-truth file, the teacher's findings are used as labels.
