import asyncio
import logging
from typing import Optional, Dict, Any
import httpx
from datetime import datetime

# Local imports
from ..database import database
from ..models import PersonalizationRequestModel, PersonalizationResponseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GroqService:
    def __init__(self):
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        self.model = "mixtral-8x7b-32768"  # Recommended for high-quality text generation
        self.temperature = 0.7
        self.max_tokens = 100

    async def is_configured(self) -> bool:
        """Check if Groq service is properly configured with API key"""
        try:
            settings = await database.get_settings()
            return bool(settings.groq_api_key)
        except Exception as e:
            logger.error(f"Error checking Groq configuration: {str(e)}")
            return False

    async def generate_personalization(self, audit_notes: str) -> PersonalizationResponseModel:
        """
        Generate a personalized opening line using Groq LLM
        Based on audit notes about the website
        """
        if not audit_notes.strip():
            error_msg = "Empty audit notes provided"
            logger.warning(error_msg)
            return PersonalizationResponseModel(
                success=False,
                error=error_msg
            )

        if not await self.is_configured():
            error_msg = "Groq API not configured - missing API key"
            logger.error(error_msg)
            return PersonalizationResponseModel(
                success=False,
                error=error_msg
            )

        try:
            settings = await database.get_settings()

            # Craft the prompt according to specifications
            system_prompt = """You are a professional business development representative.
Write a natural, conversational opening line for a cold email.
Reference specific details from the website audit.
Keep it under 2 sentences. Do not use templates or generic phrases.
Start with 'Hi' or 'Hello' and include the recipient naturally."""

            user_prompt = f"""Based on this website audit information:
{audit_notes}

Write a personalized opening line for an outreach email."""

            headers = {
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": 0.9,
                "stream": False
            }

            logger.info("Generating personalization with Groq...")

            response = await self.client.post(
                self.base_url,
                json=payload,
                headers=headers
            )

            if response.status_code != 200:
                error_msg = f"Groq API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return PersonalizationResponseModel(
                    success=False,
                    error=error_msg
                )

            response_data = response.json()

            if 'choices' not in response_data or not response_data['choices']:
                error_msg = "No choices returned from Groq API"
                logger.error(error_msg)
                return PersonalizationResponseModel(
                    success=False,
                    error=error_msg
                )

            generated_text = response_data['choices'][0]['message']['content'].strip()

            # Basic validation of response
            if not generated_text or len(generated_text.split()) < 5:
                error_msg = "Generated personalization too short or empty"
                logger.warning(error_msg)
                return PersonalizationResponseModel(
                    success=False,
                    error=error_msg
                )

            logger.info("Personalization generated successfully")
            return PersonalizationResponseModel(
                success=True,
                opening_line=generated_text
            )

        except httpx.TimeoutException:
            error_msg = "Groq API request timed out"
            logger.error(error_msg)
            return PersonalizationResponseModel(
                success=False,
                error=error_msg
            )
        except httpx.RequestError as e:
            error_msg = f"Request error communicating with Groq API: {str(e)}"
            logger.error(error_msg)
            return PersonalizationResponseModel(
                success=False,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Unexpected error in Groq personalization: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return PersonalizationResponseModel(
                success=False,
                error=error_msg
            )

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global groq_service instance
groq_service = GroqService()