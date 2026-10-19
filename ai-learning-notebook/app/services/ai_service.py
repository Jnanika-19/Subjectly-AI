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
        provider = settings.ai_provider
        if provider == "openrouter":
            api_key = settings.openrouter_api_key.strip()
            base_url = "https://openrouter.ai/api/v1"
            model = settings.openrouter_model
        elif provider == "groq":
            api_key = settings.groq_api_key.strip()
            base_url = "https://api.groq.com/openai/v1"
            model = settings.groq_model
        else:
            raise AIRequestFailedError(f"Unsupported AI_PROVIDER: {provider}")

        if not api_key:
            raise APIKeyNotConfiguredError(f"{provider.title()} API key not configured")

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.choices[0].message.content or "").strip()
        except APIKeyNotConfiguredError:
            raise
        except Exception:
            logger.exception("%s request failed", provider)
            raise AIRequestFailedError("AI request failed. Check server logs.")


ai_service = AIService()
