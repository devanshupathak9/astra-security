"""Teacher -> student loop: ties all steps together.

  teacher scan                      -> teacher findings
  student scan x N                  -> baseline recall
  teacher findings -> lessons       (single pass, leak-filtered)
  student scan + lessons x N        -> after recall
  report: before vs after (mean +- std), saved to runs/<timestamp>/
"""


def run_loop(config: dict) -> dict:
    raise NotImplementedError
