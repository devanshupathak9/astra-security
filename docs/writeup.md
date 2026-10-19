# Astra Take-Home – Write-up

Teacher → student vulnerability scanning for Android apps.
Repo: https://github.com/devanshupathak9/astra-security · Architecture: `docs/architecture.md`

---

## 1. Results: the student's recall before and after the lessons

> Fill in from `runs/<ts>/report.md` after the final run (`python main.py loop`).

| Student | Before | Placebo | After | Lift vs before | Lift vs placebo |
|---|---|---|---|---|---|
| `<STUDENT_MODEL>` | | | | | |
| `openai/gpt-oss-20b` (Groq) | | | | | |

Teacher `<TEACHER_MODEL>`: strict recall __ %, lenient __ %. Strict = right file **and** right category; lenient = right file.

**Test run so far** (teacher `gpt-oss-120b`, student `gpt-oss-20b`, both on Groq, slices strategy, 1 run):

| | Strict recall | Lenient recall | Findings |
|---|---|---|---|
| Teacher | 74% (14/19) | 100% (19/19) | 32 |
| Student before lessons | 68% (13/19) | 95% (18/19) | 27 |
| Student after lessons | – (run stopped) | – | – |

The teacher produced 12 lessons; the leak filter rejected none. Example:
*"Returning the caller's Intent as a result (e.g. setResult(RESULT_OK, getIntent())) in an exported
activity can leak all supplied extras back to the caller."*

**What I learned along the way**
- With a small teacher (`gpt-4o-mini`) on large 60k-character chunks, the teacher found only 5/19 and
  the student alone already beat it. A teacher weaker than the student cannot produce a lift, so
  teacher strength matters more than anything else.
- Large chunks made models stop after a few findings. Smaller, related chunks ("slices") helped most.
- Early student runs scored lower (9/19) partly because some chunks silently failed: the reasoning
  model spent its 2,048-token reply budget thinking and returned nothing. Fixed by raising the limit,
  and failed chunks are now counted and reported, so incomplete runs can't pass unnoticed.
- A strong student leaves little room: at 13/19 before, the possible lift is at most 6 bugs.

**Honest limits.** 19 bugs in one app is a small sample: one bug is about 5 points of recall, and
model runs vary, so the loop repeats each condition N times and reports mean ± std. The lessons
were written from this app's findings and tested on the same app, which shows they help *here*, not
that they generalize. The real test is held-out: learn lessons on app A, then measure the lift on
app B the teacher never saw (e.g. DIVA, AndroGoat, OVAA). The pipeline already supports this,
because `lessons.json` is a file you can pass to `scan --lessons` on any app.

---

## 2. The match function and why I chose it

**Rule.** A model finding matches a known bug when both are true:
1. **Same place:** the finding's file is one of the bug's files (path suffix match).
2. **Same type:** the finding's category is one of the bug's allowed categories.

Every finding and every ground-truth entry uses the same fixed list of categories (in `config.yaml`),
so the type check is a lookup, not fuzzy text matching. Each ground-truth entry lists its files and
allowed categories, e.g. `{id: 19, categories: [insecure_logging], files: [LoginActivity.java]}`.

**One-to-one.** Each bug can be claimed by at most one finding and each finding by at most one bug
(maximum bipartite matching). Reporting the same bug five times scores once; one vague finding
can't tick off three bugs.

**Two scores.**
- **Strict** = place + type. Honest lower bound.
- **Lenient** = place only. Upper bound for "right spot, wrong label": e.g. a password leaked
  through a broadcast was labelled `insecure_broadcast_receiver` instead of `implicit_intent`.

**Recall** = bugs matched / total bugs (the headline). **Precision** = findings matched / findings.

**Grounding before matching.** A finding only counts if its quoted evidence is actually found in the
code; that's also how its real file and line are filled in. Invented findings never reach matching.

**Why this design**
- Line numbers are unreliable in decompiled code, so file + type is the stable signal.
- It is deterministic, fast and explainable: no extra model calls, the same input always gives the same score.
- The lift is measured identically before and after, so systematic errors cancel out.

**Weaknesses**
- Two bugs of the same type in the same file can't be told apart (bugs 2 and 3 are both URL
  problems in one WebView activity). Next step: an LLM judge only for ambiguous pairs, logged for audit.
- Category confusion between close categories costs strict recall; lenient shows the upper bound.
- Precision counts real bugs that aren't in the 19-item list as wrong, so it is a lower bound.

**Placebo control.** Each student is also run with generic advice ("be thorough, read every file")
of the same number and length of items as the lessons. If the student improves as much with the
placebo, the gain came from a longer prompt, not from the lessons. The report shows lift vs before
**and** lift vs placebo.

---

## 3. A real app with 1M+ lines of code

InsecureShop is 23 app files. A real app is 10,000+ classes, most of them libraries. Sending
everything to a frontier model is slow, expensive and makes models skim. The approach: **cut,
prioritize, then spend the expensive model only where it matters.**

1. **Cut what isn't the app.** Already done here: only classes under the app's package are kept,
   generated code (`R`, data binding) is dropped, decompiler noise is blanked. At scale, add
   known-library detection (package names + code signatures) and list libraries with versions
   to check against vulnerability databases instead of reading them.
2. **Start from the attack surface.** The manifest says what other apps and the network can reach:
   exported components, deep links, providers, receivers. Those entry points are where
   exploitable bugs start.
3. **Slice from entry points to sinks.** Build a call/reference graph (the repo's `slices`
   strategy does a light version by class names; at scale use a real call graph). Keep only code on
   paths from untrusted input (intent extras, URIs, IPC, network) to dangerous sinks (WebView,
   startActivity, file IO, exec, SQL, logs, storage). This is a taint-style filter that turns
   1M lines into a few hundred focused slices.
4. **Cascade models by cost.** Cheap static rules (regex/semgrep for sink APIs) → small model
   triage on each slice ("anything suspicious?") → frontier model only on flagged slices.
   With a ~5–10% pass-through, frontier cost drops by 10–20×.
5. **Agentic exploration for what slices miss.** Give the model tools (read file, grep, find
   callers) and a step budget, starting from the attack surface, instead of pushing code at it.
6. **Engineering.** Cache results per file hash; on a new app version re-scan only changed
   files; run chunks in parallel within rate limits; use batch APIs for cost; dedupe across
   slices; rank by severity × confidence for human review.

---

## 4. Dynamic analysis (write-up + diagram)

```
 static scan ──► targets (exported components, deep links, suspected sinks)
                        │
                        ▼
              ┌───────────────────┐   actions    ┌────────────────────────────┐
              │   AI test agent   │ ───────────► │ emulator pool (snapshot)   │
              │ plan · act · check│ ◄─────────── │ app + Frida hooks + proxy  │
              └───────────────────┘ screen, logs └─────────────┬──────────────┘
                        │                                      │ traffic
                        ▼                                      ▼
              oracles: canary seen? ◄──────────────── live backend (test accounts)
                        │
                        ▼
              confirmed finding + reproduction trace
```

The static scan tells the agent where to look; the dynamic scan proves what actually happens.

**Confirming a vulnerability.** A crash proves nothing, so every test carries an **oracle**: a
condition that can only be true if the attack worked. The agent plants unique **canaries**: a
marker file in app storage, a fake token in the test account, a URL on a server we control.
Success means the canary shows up where it shouldn't: our server receives the marker file
(file theft), our page loads inside the app's WebView (URL injection), the token appears in
logcat or in another test app's broadcast receiver (data leak). Frida hooks on sinks (`loadUrl`,
`startActivity`, `openFile`) record whether attacker-controlled input actually reached them.

**Reaching the right screen.** The agent works from the UI hierarchy (accessibility tree plus
screenshot): it picks the next action toward a goal, logs in with seeded test accounts, fills forms
with valid data, and remembers successful paths as replayable scripts. Static analysis provides
shortcuts: exported activities and deep links can be launched directly with `adb am start`,
skipping navigation. **Coverage** = activities reached / activities in the manifest, plus method
coverage from instrumentation; the targets still unreached become the agent's next goals.

**Scale.** Emulators are flaky, so treat them as disposable: a pool of headless emulators in
containers, each restored from a clean snapshot (app installed, logged in, proxy and Frida ready)
before every test, which makes resets take seconds. A job queue spreads tests across the pool,
retries on infrastructure failures and detects flaky results by re-running once. Backend state is
reset per test through test accounts or a staging API.

**SSL pinning.** Route traffic through an intercepting proxy with its CA installed, then bypass
pinning at runtime with Frida (hook OkHttp `CertificatePinner`, `TrustManager`, the network
security config). What breaks most often: (1) pinning in native code or custom TLS stacks
(Flutter, Cronet), which Java hooks don't reach; (2) root, emulator and Frida detection, which make
the app refuse to run; (3) mutual TLS, or certificate checks done server-side.

**A bug only dynamic analysis catches: IDOR / broken object-level authorization.** Changing
`order_id=1001` to `1002` in an API call returns another user's order. The bug lives in the
backend's authorization logic, which isn't in the APK, so static analysis can't see it. An agent
with two test accounts can try it and confirm it with the canary in the other account.

---

## 5. Models and why

| Role | Model | Why |
|---|---|---|
| Teacher | `<TEACHER_MODEL>` (OpenAI) | A strong frontier model: the teacher's recall caps everything the student can learn. |
| Student | `<STUDENT_MODEL>` (OpenAI, smallest/cheapest) | Cheap and fast with no free-tier rate limits, so many runs are affordable. |
| Open student | `openai/gpt-oss-20b` on Groq | OpenAI's open-weight model, the kind of model Astra would self-host at scale; free tier. |
| Test teacher | `openai/gpt-oss-120b` on Groq | Free, used while building and testing the pipeline. |

All model ids, keys and endpoints come from `.env`; switching any of them is a `.env` change. The
model layer is one small interface (`LLM.ask_json`) with one class per provider: OpenAI-compatible
APIs (OpenAI, Groq, Together, Ollama, vLLM) and Anthropic. Adding a provider is one class plus one
registry line.

Practical notes: reasoning models need a large reply limit (they think before answering);
Groq's free tier allows about 8k tokens per minute for `gpt-oss-20b`, so a student scan takes
~15 minutes there; newer OpenAI models only accept their default temperature, so temperature is
optional in config.

---

## 6. Optional: frontier scan on a real APK

Not done in the time available. Plan: `python main.py scan --model teacher --app <real.apk>` (no
ground truth → findings saved for manual review), then label each finding real / noise.
