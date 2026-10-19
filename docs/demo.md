# Demo Script (3–5 minutes)

Record your screen with a terminal and an editor open in the repo. Talk through each step.

**Before recording:** run `./run_all.sh --free` once so a finished run exists (it takes about an hour);
in the demo you show its outputs instead of waiting.

---

### 1. The problem (30 s)
Open `docs/problem_statement.md`.
> "A strong teacher model finds vulnerabilities, writes general lessons, and a cheap open student
> model should get better with them. I measure how much."

### 2. Ingest (45 s)
```bash
python main.py ingest
```
> "jadx decompiles the APK. I parse the manifest to find what other apps can reach – 8 exported
> components – and keep only the app's own code: 23 files out of about 2,200."

### 3. How code is passed to the model (30 s)
```bash
python main.py chunks --strategy slices --model student
```
> "Each request is one entry point plus the files it uses, so bugs that span files are seen together.
> Every request starts with the list of exported components."

### 4. A scan and its findings (45 s)
Open `runs/<time>/teacher_findings.json`.
> "Each finding has type, file, line, severity and the exact code quote. Findings whose quote isn't
> in the code are dropped, so invented findings never count."

### 5. Lessons (30 s)
Open `runs/<time>/lessons.json`.
> "One teacher call turns its findings into general rules. Any rule that names a class or package
> from this app is rejected automatically."

### 6. The result (60 s)
Open `runs/<time>/report.md`.
> "Before, placebo, after. The placebo is generic advice of the same length – it shows whether
> the gain comes from the lessons or just from a longer prompt. Strict means right file and right
> bug type; lenient means right file. Matching is one-to-one, so duplicates can't inflate recall."

### 7. Extensibility (30 s)
Open `.env.example` and `astra/llm.py`.
> "Models are chosen in `.env`; switching OpenAI ↔ Groq is a three-line change. The model layer
> is one interface with a class per provider. A new app is `--app other.apk`."
