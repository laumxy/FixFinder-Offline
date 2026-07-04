import time

import requests
from urllib.parse import urlsplit, urlunsplit

from fixfinder_engine.config import settings

# How long (seconds) a cached "available" result is trusted before re-checking
_AVAILABILITY_TTL = 30.0


class QwenClient:
    def __init__(self) -> None:
        self.last_error: str = ""
        # Cached availability state so converse() doesn't make a redundant HTTP
        # GET before every generate() call.
        self._available: bool | None = None
        self._available_checked_at: float = 0.0

    # ── Public ────────────────────────────────────────────────────────────────

    def health(self) -> dict:
        if not settings.use_ollama:
            return {
                "enabled": False,
                "available": False,
                "model": settings.ollama_model,
                "message": "Ollama integration disabled by FIXFINDER_USE_OLLAMA.",
            }

        tags_url = self._api_url("/api/tags")
        try:
            response = requests.get(tags_url, timeout=5)
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = {model.get("name", "") for model in models}
            available = settings.ollama_model in model_names
            self._set_cached_availability(available)
            return {
                "enabled": True,
                "available": available,
                "server_url": self._server_url(),
                "generate_url": settings.ollama_url,
                "model": settings.ollama_model,
                "installed_models": sorted(name for name in model_names if name),
                "message": "Ollama is ready." if available else f"Model {settings.ollama_model} is not installed.",
            }
        except requests.RequestException as exc:
            self._set_cached_availability(False)
            return {
                "enabled": True,
                "available": False,
                "server_url": self._server_url(),
                "generate_url": settings.ollama_url,
                "model": settings.ollama_model,
                "installed_models": [],
                "message": f"Ollama server is not reachable: {exc}",
            }

    def is_available(self) -> bool:
        """
        Return cached availability, refreshing at most once every
        _AVAILABILITY_TTL seconds.  Much cheaper than a full health() call
        when invoked inside the hot request path.
        """
        if not settings.use_ollama:
            return False
        now = time.monotonic()
        if self._available is None or (now - self._available_checked_at) > _AVAILABILITY_TTL:
            # Refresh cache via a lightweight /api/tags ping
            self.health()
        return bool(self._available)

    def generate(self, prompt: str) -> str:
        self.last_error = ""
        if not settings.use_ollama:
            return ""

        # Cap token generation to keep individual LLM calls well within budget.
        num_predict = min(
            getattr(settings, "ollama_num_predict", 512),
            512,
        )

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": settings.ollama_temperature,
                "num_predict": num_predict,
            },
        }

        # Honour the configured timeout but cap it so a slow model can't
        # blow the 50-second budget on its own.
        timeout = min(
            getattr(settings, "ollama_timeout_seconds", 40),
            40,
        )

        try:
            response = requests.post(
                settings.ollama_url,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            # Mark as available after a successful call
            self._set_cached_availability(True)
            return str(data.get("response", "")).strip()
        except requests.RequestException as exc:
            self.last_error = str(exc)
            # Invalidate cache on failure so the next call re-probes
            self._set_cached_availability(False)
            return ""

    # ── Private ───────────────────────────────────────────────────────────────

    def _set_cached_availability(self, available: bool) -> None:
        self._available = available
        self._available_checked_at = time.monotonic()

    def _server_url(self) -> str:
        parts = urlsplit(settings.ollama_url)
        return urlunsplit((parts.scheme, parts.netloc, "", "", ""))

    def _api_url(self, path: str) -> str:
        return f"{self._server_url()}{path}"
