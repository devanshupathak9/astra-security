# Problem Statement – Astra Take-Home Assignment

## Context

At Astra, we teach frontier models to pentest like our best researchers, then teach cheaper open
models to match them so we can run at scale. This assignment is a small, real slice of that work.
It is v0.1, so we care more about a working end-to-end slice, and about how you think, than
about polish.

**Time:** 3 to 4 days.

## What to build

You get the following:

- **Decompiled app.** Download the APK from the releases page
  (https://github.com/hax0rgb/InsecureShop/releases) and decompile it yourself. Treat the
  decompiled output as your input.
- **Ground-truth vulnerability list.** Use the 19 vulnerabilities in the repo README's
  "Vulnerabilities" section (https://github.com/hax0rgb/InsecureShop#vulnerabilities).
- **Starter repo.** We're not providing one. Wire up the clients yourself
  (Anthropic/OpenAI/Gemini for the teacher, Groq or similar for the student). Keep the
  model layer behind a small interface so adding a model is a config change. Extensibility
  is one of the judging criteria, so this is a fair part of the exercise.

**Target app:** InsecureShop (https://github.com/hax0rgb/InsecureShop). The APK is on the
releases page.

Make these three components work together:

1. **Ingest.** Load the decompiled app: manifest, code, and resources.
2. **Frontier scan.** Scan the code for vulnerabilities using Claude or OpenAI. Return
   structured findings with type, location, severity, and evidence.
3. **Teacher-to-student loop.** Run the same scan with an open model, then:
   - Have the frontier model turn its findings into general lessons in a single pass.
   - Feed those lessons to the open model and rescan.
   - Measure how much the open model's recall improves.

Lessons must be general rules, never instance-specific. "Flag line 12 of FileX" is not
acceptable. "Exported components that accept an intent extra without validating it are a risk" is.

**Matching.** Decide how you match two findings (for example, a model finding against a
ground-truth entry), and explain your reasoning. Be honest about the limits of one app: it cannot
prove that your lessons generalize. We will discuss held-out testing in the interview.

## Dynamic analysis (write, don't build)

The build is static, but we also want to see that you understand dynamic scanning. In 300 to
500 words, plus a simple architecture diagram, describe how you would extend this system
into a dynamic scan run by an AI agent against an app with a live backend. Also name one bug
type that dynamic analysis catches and static analysis cannot.

Cover:

- **Confirming a vulnerability.** How does the agent know at runtime that a vulnerability
  actually occurred, rather than just that the app crashed?
- **Reaching the right screen.** Bugs often sit behind logins, forms, and several taps.
  How does the agent navigate there, and how would you measure coverage?
- **Scale.** Emulators are slow, flaky, and need a clean reset for every run. How do you
  run this at scale?
- **SSL pinning.** How do you handle it to see traffic, and what are the two or three
  things most likely to break?

We care about how well you understand the hard parts, not about the tool list or a polished
diagram.

## Bring your own models

- **Teacher:** any strong hosted model, using your Anthropic or OpenAI trial credit or a
  free tier such as Google AI Studio.
- **Student:** any open model. Groq's free tier needs no card.

The task is cheap enough to run on free credit. Use a Sonnet-class or smaller model to stay
within it.

## What to send back

1. The repo, containing ingest, scan, and the learning loop.
2. A Google Doc covering:
   - Your match function and why you chose it
   - How you would handle a real app with 1M+ lines of code
   - The dynamic analysis write-up and diagram
   - Which models you used and why
3. The open model's recall before and after the lessons.
4. Optional: run the frontier scan on one real APK and report how many findings were
   real versus noise, and what broke.
5. Optional: a short demo.

## How we will judge it

- Real findings
- Clean code that is easy to extend to more models and apps
- Above all, a real, honestly measured recall lift with a sensible match function
- On the dynamic section, your understanding of the hard problems

**Important:** we will evaluate your harness and teacher-student pipeline by running it on a
different APK that you have not seen, scanning first with the top model and then with the
small model. Your tool should therefore run on a new app with minimal changes. Keep model
choice, app path, and thresholds in config, and don't hard-code anything specific to
InsecureShop.
