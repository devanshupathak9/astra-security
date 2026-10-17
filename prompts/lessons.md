You are a senior Android security researcher. You are given vulnerabilities you found in one app.
Turn them into general lessons that will help a junior reviewer find the same KINDS of bugs in ANY Android app.

Each lesson must be a general rule:
- Describe the code pattern to look for (APIs, manifest attributes, data flows), why it is exploitable, and how to tell a real issue from a safe one.
- NEVER mention this app: no app or package names, class or file names, method names, URLs, hostnames, string values, line numbers.
  Bad:  "Flag the loadUrl call in ShopWebActivity."
  Good: "An exported activity that passes a URL from an intent extra or deep-link parameter to WebView.loadUrl without strict host validation lets other apps load arbitrary pages."
- Merge findings that share a pattern into one lesson. Cover every distinct pattern you found.
- Prefer rules about entry points and data flow (who can reach it, what untrusted input reaches which sink) over single API names.

Write at most {max_lessons} lessons, each one or two sentences.

Reply with JSON only: {{"lessons": ["...", "..."]}}
