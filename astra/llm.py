"""Model layer: the only place that talks to an LLM API.

    LLM                    base class: retries, JSON parsing, token counting (shared by all)
     ├── OpenAICompatibleLLM   OpenAI, Groq, Together, Ollama, vLLM, ... (one API shape)
     └── AnthropicLLM          Claude, through Anthropic's own SDK

The rest of the code only calls `llm.ask_json(system, user)` and never knows which provider it is.
Adding a provider = one subclass with a `_complete` method + one line in PROVIDERS.
Choosing a provider/model = config.yaml (`provider:` and `model:`).
"""
import json
import os
import re
import time
from abc import ABC, abstractmethod


class LLM(ABC):
    """Shared behaviour. Subclasses only implement `_complete`."""

    def __init__(self, model: str, api_key_env: str, temperature: float | None = 0.0,
                 max_chunk_chars: int = 20000, max_tokens: int = 8192,
                 params: dict | None = None, **_):
        self.model = model
        self.api_key = os.environ.get(api_key_env, "")
        if not self.api_key:
            raise ValueError(f"{api_key_env} is not set: add it to .env")
        self.temperature = temperature          # None = use the model's default
        self.max_chunk_chars = max_chunk_chars  # how much code fits in one request (used by the chunker)
        self.max_tokens = max_tokens            # reply limit; reasoning models need room to think
        self.params = params or {}              # provider-specific extras, e.g. reasoning_effort
        self.usage = {"input": 0, "output": 0}

    @abstractmethod
    def _complete(self, system: str, user: str) -> tuple[str, int, int]:
        """Send one request. Return (reply text, input tokens, output tokens)."""

    def ask_json(self, system: str, user: str, retries: int = 5) -> dict:
        """Send a prompt and return the reply as a dict. Retries on errors and bad JSON."""
        for attempt in range(retries):
            try:
                text, tokens_in, tokens_out = self._complete(system, user)
                self.usage["input"] += tokens_in
                self.usage["output"] += tokens_out
                return parse_json(text)
            except Exception as e:
                if attempt == retries - 1:
                    raise
                # Rate limits (429) need a real pause for the per-minute quota to refill
                rate_limited = "429" in str(e) or "rate limit" in str(e).lower()
                time.sleep(15 * 2 ** attempt if rate_limited else 5 * (attempt + 1))

    def _optional_args(self) -> dict:
        """Arguments sent only when set: temperature (if not None) and any extra params."""
        args = {"temperature": self.temperature} if self.temperature is not None else {}
        return {**args, **self.params}


class OpenAICompatibleLLM(LLM):
    """Any API that speaks the OpenAI chat format: OpenAI, Groq, Together, Ollama, vLLM, ..."""

    def __init__(self, base_url: str | None = None, **kwargs):
        super().__init__(**kwargs)
        from openai import OpenAI
        # The SDK retries rate-limit (429) errors itself, waiting as long as the server asks
        self.client = OpenAI(api_key=self.api_key, base_url=base_url, max_retries=6)

    def _complete(self, system, user):
        resp = self.client.chat.completions.create(
            model=self.model,
            max_completion_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            **self._optional_args(),
        )
        usage = resp.usage
        return (resp.choices[0].message.content or "",
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0)


class AnthropicLLM(LLM):
    """Claude models through Anthropic's SDK (pip install anthropic)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from anthropic import Anthropic
        self.client = Anthropic(api_key=self.api_key, max_retries=6)

    def _complete(self, system, user):
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            **self._optional_args(),
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        return text, resp.usage.input_tokens, resp.usage.output_tokens


# config.yaml `provider:` value -> class
PROVIDERS = {
    "openai": OpenAICompatibleLLM,
    "anthropic": AnthropicLLM,
}


def get_llm(config: dict, role: str) -> LLM:
    """role is a key under `models` in config.yaml, e.g. 'teacher' or 'student'."""
    settings = dict(config["models"][role])
    if not settings.get("model"):
        raise ValueError(f"No model id for '{role}': set {role.upper()}_MODEL in .env "
                         f"(list ids with: python main.py models --model {role})")
    provider = settings.pop("provider", "openai")
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r} for {role}, expected one of {list(PROVIDERS)}")
    return PROVIDERS[provider](**settings)


def parse_json(text: str) -> dict:
    """Parse a JSON reply, tolerating ```json fences or text around the object."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start:end + 1])
