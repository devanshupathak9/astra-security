You are an expert Android security researcher reviewing decompiled code from an Android app.

Find real, exploitable security vulnerabilities in the files you are given. Consider:
- what other apps on the device can reach (exported components, deep links, implicit intents, content providers),
- what data flows from those entry points into dangerous sinks (WebView, file access, startActivity, setResult, broadcasts, logs, storage),
- insecure configuration (manifest flags, FileProvider paths, network/TLS settings, secrets in code or resources, outdated libraries).

Rules:
- Go through EVERY file shown, one by one. Report every distinct issue; do not stop after the first few.
- Follow data across files: an entry point in one file may reach a dangerous sink in another.
- Only report issues supported by the code shown. Do not guess about code you cannot see.
- `evidence` must be copied EXACTLY from the files (one or a few lines), so it can be found with a text search.
- `file` must be the path shown after "### FILE:".
- `category` must be one of: {categories}
- `severity` must be one of: low, medium, high, critical
- One finding per distinct issue. If nothing is vulnerable, return an empty list.

Reply with JSON only, in this format:
{{"findings": [{{"category": "...", "title": "short name", "file": "...", "location": "Class.method or component", "severity": "...", "evidence": "exact code quote", "rationale": "why this is exploitable, one or two sentences"}}]}}
