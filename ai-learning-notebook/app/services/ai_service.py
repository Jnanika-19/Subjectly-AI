from __future__ import annotations

import logging

from openai import OpenAI

from app.core.config import settings


logger = logging.getLogger(__name__)


class APIKeyNotConfiguredError(RuntimeError):
    pass


class AIRequestFailedError(RuntimeError):
    pass


class AIService:
    def generate_answer(self, prompt: str) -> str:
        api_key = settings.groq_api_key.strip()
        if not api_key:
            raise APIKeyNotConfiguredError("API key not configured")

        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            response = client.responses.create(
                model=settings.groq_model,
                input=prompt,
            )
            return (response.output_text or "").strip()
        except APIKeyNotConfiguredError:
            raise
        except Exception:
            logger.exception("Groq request failed")
            raise AIRequestFailedError("AI request failed. Check server logs.")


ai_service = AIService()
