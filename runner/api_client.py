"""
api_client.py — Unified API client for DeepSeek and Gemini.
DeepSeek uses OpenAI-compatible format.
Gemini uses Google's native REST API.
"""

import os
import time
import json
import requests
from dataclasses import dataclass, field


@dataclass
class APIResponse:
    content: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    raw_usage: dict = field(default_factory=dict)
    error: str = ""


class DeepSeekClient:
    """OpenAI-compatible client for DeepSeek."""

    def __init__(self, config: dict):
        self.base_url = config["base_url"].rstrip("/")
        self.api_key = config["api_key_env"]
        self.model = config["name"]
        self.max_tokens = config.get("max_tokens", 16384)
        self.temperature = config.get("temperature", None)

    def chat(self, system_prompt: str, messages: list[dict]) -> APIResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": all_messages,
            "max_tokens": self.max_tokens,
            #
            "stream": False,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        t0 = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=300)
            latency_ms = int((time.time() - t0) * 1000)
            data = resp.json()

            if "error" in data:
                return APIResponse(error=json.dumps(data["error"]), latency_ms=latency_ms)

            choice = data["choices"][0]["message"]
            usage = data.get("usage", {})

            return APIResponse(
                content=choice.get("content", ""),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=latency_ms,
                raw_usage=usage,
            )
        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            return APIResponse(error=str(e), latency_ms=latency_ms)


class GeminiClient:
    """Native Google Gemini REST API client."""

    def __init__(self, config: dict):
        self.base_url = config["base_url"].rstrip("/")
        self.api_key = config["api_key_env"]
        self.model = config["name"]
        self.max_tokens = config.get("max_tokens", 16384)
        self.temperature = config.get("temperature", None)

    def chat(self, system_prompt: str, messages: list[dict]) -> APIResponse:
        url = (
            f"{self.base_url}/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        headers = {"Content-Type": "application/json"}

        # Build Gemini-format contents
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                #
            },
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        # System instruction goes in a separate field
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        t0 = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=300)
            latency_ms = int((time.time() - t0) * 1000)
            data = resp.json()

            if "error" in data:
                return APIResponse(error=json.dumps(data["error"]), latency_ms=latency_ms)

            # Extract text from candidates
            candidates = data.get("candidates", [])
            if not candidates:
                return APIResponse(error="No candidates in response", latency_ms=latency_ms)

            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)

            # Extract token usage
            usage_meta = data.get("usageMetadata", {})
            prompt_tokens = usage_meta.get("promptTokenCount", 0)
            completion_tokens = usage_meta.get("candidatesTokenCount", 0)
            total_tokens = usage_meta.get("totalTokenCount", 0)

            return APIResponse(
                content=text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                raw_usage=usage_meta,
            )
        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            return APIResponse(error=str(e), latency_ms=latency_ms)
class GPTClient:
    """OpenAI-compatible client for GPT models."""

    def __init__(self, config: dict):
        self.base_url = config["base_url"].rstrip("/")
        self.api_key = config["api_key_env"]
        self.model = config["name"]
        self.max_tokens = config.get("max_tokens", 16384)
        self.temperature = config.get("temperature", None)

    def chat(self, system_prompt: str, messages: list[dict]) -> APIResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": all_messages,
            "max_tokens": self.max_tokens,
            # "temperature": self.temperature,
            "stream": False,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        t0 = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=300)
            latency_ms = int((time.time() - t0) * 1000)
            data = resp.json()

            if "error" in data:
                return APIResponse(error=json.dumps(data["error"]), latency_ms=latency_ms)

            choice = data["choices"][0]["message"]
            usage = data.get("usage", {})

            return APIResponse(
                content=choice.get("content", ""),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                latency_ms=latency_ms,
                raw_usage=usage,
            )
        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            return APIResponse(error=str(e), latency_ms=latency_ms)

def create_client(model_config: dict):
    """Factory: return the right client based on provider."""
    provider = model_config["provider"]
    if provider == "deepseek":
        return DeepSeekClient(model_config)
    elif provider == "gemini":
        return GeminiClient(model_config)
    elif provider == "openai":
        return GPTClient(model_config)
    else:
        raise ValueError(f"Unknown provider: {provider}")
