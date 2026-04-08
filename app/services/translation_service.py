from __future__ import annotations

import json
import logging
import ssl
from urllib import error, parse, request

import certifi

from app.config import Settings


logger = logging.getLogger(__name__)


class TranslationService:
    free_api_url = "https://api-free.deepl.com/v2/translate"
    pro_api_url = "https://api.deepl.com/v2/translate"
    target_language_map = {
        "en": "EN",
        "ru": "RU",
        "uk": "UK",
    }

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def is_enabled(self) -> bool:
        return bool(self.settings.deepl_api_key)

    def _resolve_api_url(self) -> str:
        configured = (self.settings.deepl_api_url or "").strip()
        if configured:
            return configured
        if self.settings.deepl_api_key.endswith(":fx"):
            return self.free_api_url
        return self.pro_api_url

    def translate_text(self, text: str | None, target_language: str) -> str | None:
        value = (text or "").strip()
        if not value:
            return text
        if target_language == "en" or not self.is_enabled():
            return text
        deepl_target = self.target_language_map.get(target_language)
        if not deepl_target:
            return text
        try:
            payload = parse.urlencode(
                {
                    "text": value,
                    "target_lang": deepl_target,
                    "preserve_formatting": "1",
                }
            ).encode("utf-8")
            req = request.Request(
                self._resolve_api_url(),
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"DeepL-Auth-Key {self.settings.deepl_api_key}",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=15, context=self.ssl_context) as response:
                body = json.loads(response.read().decode("utf-8"))
            translations = body.get("translations") or []
            if not translations:
                return text
            return translations[0].get("text") or text
        except error.HTTPError as exc:
            try:
                response_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                response_body = ""
            logger.error(
                "deepl_translation_failed target_language=%s status=%s api_url=%s response=%s",
                target_language,
                exc.code,
                self._resolve_api_url(),
                response_body[:500],
            )
            return text
        except Exception:
            logger.exception(
                "deepl_translation_failed target_language=%s api_url=%s",
                target_language,
                self._resolve_api_url(),
            )
            return text
