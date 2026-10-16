"""Model layer: the only place that talks to an LLM API.

Every model (OpenAI, Groq, Together, Ollama, vLLM, ...) is reached through the
OpenAI-compatible chat API, so a new model is a new entry in config.yaml.
A provider with a different API would be a second class with the same `ask_json` method.
"""
import json
import os

from openai import OpenAI


class LLM:
    def __init__(self, model: str, api_key_env: str, base_url: str | None = None,
                 temperature: float = 0.0, max_chunk_chars: int = 20000, **_):
        self.model = model
        self.temperature = temperature
        self.max_chunk_chars = max_chunk_chars
        self.client = OpenAI(api_key=os.environ[api_key_env], base_url=base_url)

    def ask_json(self, system: str, user: str) -> dict:
        """Send a prompt and return the model's reply parsed as JSON."""
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return json.loads(resp.choices[0].message.content)


def get_llm(config: dict, role: str) -> LLM:
    """role is a key under `models` in config.yaml, e.g. 'teacher' or 'student'."""
    return LLM(**config["models"][role])
