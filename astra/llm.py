"""Model layer: the only place that talks to an LLM API.

Every model (OpenAI, Groq, Together, Ollama, vLLM, ...) is reached through the
OpenAI-compatible chat API, so a new model is a new entry in config.yaml.
A provider with a different API would be a second class with the same `ask_json` method.
"""
import json
import os
import time

from openai import OpenAI


class LLM:
    def __init__(self, model: str, api_key_env: str, base_url: str | None = None,
                 temperature: float | None = 0.0, max_chunk_chars: int = 20000,
                 max_tokens: int = 8192, params: dict | None = None, **_):
        self.model = model
        self.temperature = temperature
        self.max_chunk_chars = max_chunk_chars
        # Reasoning models think before answering; too small a limit leaves an empty reply
        self.max_tokens = max_tokens
        self.params = params or {}          # provider-specific extras, e.g. reasoning_effort
        self.usage = {"input": 0, "output": 0}
        # The SDK retries rate-limit (429) errors itself, waiting as long as the server asks
        self.client = OpenAI(api_key=os.environ[api_key_env], base_url=base_url, max_retries=6)

    def ask_json(self, system: str, user: str, retries: int = 3) -> dict:
        """Send a prompt and return the model's reply parsed as JSON (retries on errors)."""
        for attempt in range(retries):
            try:
                optional = {"temperature": self.temperature} if self.temperature is not None else {}
                resp = self.client.chat.completions.create(
                    model=self.model,
                    max_completion_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    **optional,
                    **self.params,
                )
                if resp.usage:
                    self.usage["input"] += resp.usage.prompt_tokens
                    self.usage["output"] += resp.usage.completion_tokens
                return json.loads(resp.choices[0].message.content)
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(5 * (attempt + 1))   # e.g. reply was empty or not valid JSON


def get_llm(config: dict, role: str) -> LLM:
    """role is a key under `models` in config.yaml, e.g. 'teacher' or 'student'."""
    return LLM(**config["models"][role])
