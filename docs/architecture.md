# Architecture

## Overview

A static vulnerability scanner for Android apps, built to measure one thing: can a strong
**teacher** model make a cheap **student** model better at finding bugs by giving it general
**lessons**?

```
            ┌────────────────────────── config.yaml ──────────────────────────┐
            │  app path · models · strategy · thresholds · categories         │
            └─────────────────────────────────────────────────────────────────┘

  APK / decompiled folder
          │
          ▼
   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
   │   INGEST    │ App  │   CHUNKER   │chunks│    SCAN     │  findings
   │ jadx, parse │─────►│ fit context │─────►│ model + JSON│──────────┐
   │ manifest    │      │ window      │      │ + evidence  │          │
   └─────────────┘      └─────────────┘      │   check     │          │
                                             └──────▲──────┘          │
                                                    │ lessons         ▼
                                             ┌──────┴──────┐   ┌─────────────┐
                                             │   LESSONS   │   │    MATCH    │
                                             │ teacher →   │   │ vs ground   │
                                             │ general     │   │ truth →     │
                                             │ rules       │   │ recall      │
                                             └─────────────┘   └─────────────┘
```

## Components

| Component | File | In → Out | Job |
|---|---|---|---|
| Ingest | `astra/ingest.py` | APK → `App` | Decompile, list components and what is exported, keep app code only, collect resources and libraries |
| Chunker | `astra/chunker.py` | `App` → `Chunk[]` | Split the app into model-sized requests; every chunk carries the attack-surface header |
| Model layer | `astra/llm.py` | prompt → JSON | The only code that calls an LLM API |
| Scan | `astra/scan.py` | `Chunk[]` → `Finding[]` | Ask the model per chunk, keep findings whose evidence exists in the code, dedupe |
| Lessons | `astra/lessons.py` | `Finding[]` → rules | Teacher writes general rules in one call; app-specific ones are rejected |
| Match | `astra/match.py` | `Finding[]` + ground truth → scores | One-to-one matching, strict/lenient recall, precision |
| Loop | `astra/loop.py` | everything → report | Runs the teacher → student experiment end to end |

## The experiment

```
1. teacher scan                 → teacher findings
2. student scan (no lessons)    → recall BEFORE
3. teacher findings → lessons   (one call, leak-filtered)
4. student scan (with lessons)  → recall AFTER
5. compare BEFORE vs AFTER
```

## Design principles

- **Config over code.** Models, app, strategy and thresholds live in `config.yaml`; nothing app-specific is hard-coded.
- **One job per module.** Each step reads the previous step's output and can run on its own from the CLI.
- **Verify, don't trust.** Model output is checked against the real code before it counts.
- **Everything is saved.** Each run writes its findings, lessons and report to `runs/<timestamp>/`.
