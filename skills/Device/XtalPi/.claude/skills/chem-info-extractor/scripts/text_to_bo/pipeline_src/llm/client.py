import json
import os
import re
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from pipeline_src.llm.cache import load_cache, make_cache_key, get_cached, save_cache
from pipeline_src.llm.validator import validate_schema


# --- FounDryClaw 密钥管理 key (same block in every FounDryClaw device skill script) ---
PLATFORM_MODEL = "gpt-6-luna"
PLATFORM_KEY_MISSING = (
    "未在 FounDryClaw“密钥管理”中找到 OPENAI-API-KEY：请在 设置 → 密钥管理 中添加 "
    "OPENAI-API-KEY（接口地址和 API Key）后重试。"
)


class PlatformKeyError(RuntimeError):
    """Inside FounDryClaw the 密钥管理 OPENAI-API-KEY is required; raised when it is
    missing or cannot be read. There is deliberately no fallback to .env there."""


def _trust_system_ca_store() -> None:
    """Windows only: also trust the OS certificate store. Antivirus HTTPS scanning (e.g. Avast Web/Mail
    Shield) re-signs traffic with a root that only the OS store knows, so certifi alone fails with
    CERTIFICATE_VERIFY_FAILED. Verification stays on; the OS roots are merged into a CA bundle."""
    if sys.platform != "win32" or os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import ssl
        import tempfile

        import certifi

        pems = [Path(certifi.where()).read_text(encoding="utf-8")]
        for store in ("ROOT", "CA"):
            for cert, encoding, _trust in ssl.enum_certificates(store):
                if encoding == "x509_asn":
                    pems.append(ssl.DER_cert_to_PEM_cert(cert))
        bundle = Path(tempfile.gettempdir()) / "foundryclaw_ca_bundle.pem"
        bundle.write_text("\n".join(pems), encoding="utf-8")
        os.environ["REQUESTS_CA_BUNDLE"] = os.environ["SSL_CERT_FILE"] = str(bundle)
    except Exception:
        pass  # keep the default bundle



@lru_cache(maxsize=None)
def platform_llm_config(model_env: str) -> "tuple[str, str, str] | None":
    """(base_url, api_key, model) from the invoking user's OPENAI-API-KEY in 密钥管理,
    model gpt-6-luna unless the model_env variable overrides it. Returns None outside
    FounDryClaw (FOUNDRYCLAW_MODEL_ROUTER_* unset), where the .env settings apply."""
    base = str(os.environ.get("FOUNDRYCLAW_MODEL_ROUTER_BASE_URL") or "").strip()
    token = str(os.environ.get("FOUNDRYCLAW_MODEL_ROUTER_TOKEN") or "").strip()
    if not base or not token:
        return None
    _trust_system_ca_store()
    request = urllib.request.Request(
        base.rstrip("/") + "/api/model-router/internal/openai-key",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError) as exc:
        raise PlatformKeyError(f"无法从 FounDryClaw 读取“密钥管理”中的 OPENAI-API-KEY：{exc}") from exc
    if not isinstance(payload, dict) or not payload.get("configured"):
        raise PlatformKeyError(PLATFORM_KEY_MISSING)
    base_url = str(payload.get("base_url") or "").strip()
    api_key = str(payload.get("api_key") or "").strip()
    if not base_url or not api_key:
        raise PlatformKeyError(PLATFORM_KEY_MISSING)
    return base_url, api_key, os.getenv(model_env) or PLATFORM_MODEL
# --- end FounDryClaw 密钥管理 key ---


class LLMClient:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.base_url = os.getenv(config["base_url_env"], "").strip() or None
        self.api_key = os.getenv(config["api_key_env"], "").strip() or None
        self.model = os.getenv(config["model_env"], "").strip() or None
        temperature_text = os.getenv(config["temperature_env"], "").strip()
        self.temperature = float(temperature_text) if temperature_text else None
        platform = platform_llm_config("CHEM_INFO_EXTRACTOR_MODEL")
        if platform:
            # FounDryClaw: the user's 密钥管理 key and gpt-6-luna, which rejects `temperature`,
            # so it is not sent (the value below only keeps the cache key stable).
            self.base_url, self.api_key, self.model = platform
            if self.temperature is None:
                self.temperature = 0.0
        self.send_temperature = platform is None
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
        request: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": response_format,
        }
        if self.send_temperature:
            request["temperature"] = self.temperature
        response = self._client.chat.completions.create(**request)
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
