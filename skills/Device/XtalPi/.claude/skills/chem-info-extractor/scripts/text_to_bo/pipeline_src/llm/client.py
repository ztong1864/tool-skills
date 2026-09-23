import json
import os
import re
from typing import Any, Dict, Optional, Tuple

from pipeline_src.llm.cache import load_cache, make_cache_key, get_cached, save_cache
from pipeline_src.llm.validator import validate_schema


class LLMClient:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.base_url = os.getenv(config["base_url_env"], "").strip() or None
        self.api_key = os.getenv(config["api_key_env"], "").strip() or None
        self.model = os.getenv(config["model_env"], "").strip() or None
        temperature_text = os.getenv(config["temperature_env"], "").strip()
        self.temperature = float(temperature_text) if temperature_text else None
        self.max_retries = int(config.get("max_retries", 2))
        self.request_timeout_seconds = float(config.get("request_timeout_seconds", 120))
        self.cache_dir = config.get("cache_dir")
        self.cache_path = os.path.join(self.cache_dir, "llm_cache.jsonl") if self.cache_dir else None
        self._cache = load_cache(self.cache_path) if self.cache_path else {}

        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            raise ImportError("openai package is required for LLMClient.") from exc

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        if not self.base_url:
            raise ValueError("OPENAI_BASE_URL is not set.")
        if not self.model:
            raise ValueError("OPENAI_MODEL is not set.")
        if self.temperature is None:
            raise ValueError("OPENAI_TEMPERATURE is not set.")
        if not (self.base_url.startswith("http://") or self.base_url.startswith("https://")):
            raise ValueError(
                f"OPENAI_BASE_URL must start with 'http://' or 'https://'. Got: {self.base_url!r}"
            )
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.request_timeout_seconds,
        )

    def _save_success(self, payload: Dict[str, Any], response: Dict[str, Any]) -> None:
        if not self.cache_path:
            return
        save_cache(self.cache_path, payload, response)
        self._cache[make_cache_key(payload)] = {"payload": payload, "response": response}

    def _parse_json_content(self, content: str) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = content[start : end + 1].strip()
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass

        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, flags=re.DOTALL)
        if fenced:
            return json.loads(fenced.group(1))

        raise json.JSONDecodeError("Unable to parse JSON response", content, 0)

    def _chat(self, system_prompt: str, user_prompt: str, response_format: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_format,
            temperature=self.temperature,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response content from LLM.")
        return self._parse_json_content(content)

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        cache_namespace: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        payload = {
            "system": system_prompt,
            "user": user_prompt,
            "model": self.model,
            "temperature": self.temperature,
            "schema": schema,
            "namespace": cache_namespace,
        }
        cache_key = make_cache_key(payload)
        cached = get_cached(self._cache, cache_key)
        if cached is not None:
            return cached, {"cached": True, "errors": []}

        errors = []
        last_result: Dict[str, Any] | None = None
        for _ in range(self.max_retries + 1):
            try:
                result = self._chat(system_prompt, user_prompt, {"type": "json_object"})
            except (json.JSONDecodeError, ValueError) as exc:
                errors = [f"parse_error:{exc}"]
                continue
            except Exception as exc:
                errors = [f"request_error:{type(exc).__name__}:{exc}"]
                continue

            last_result = result
            if schema is None:
                self._save_success(payload, result)
                return result, {"cached": False, "errors": []}
            ok, errs = validate_schema(result, schema)
            if ok:
                self._save_success(payload, result)
                return result, {"cached": False, "errors": []}
            errors = errs

        if last_result is None:
            raise RuntimeError(f"LLM request failed after retries: {errors}")
        return last_result, {"cached": False, "errors": errors}
