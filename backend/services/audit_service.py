import asyncio
import logging
from typing import Optional, Dict, Any
import httpx
from datetime import datetime

# Local imports
from ..database import database
from ..models import AuditRequestModel, AuditResponseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self):
        self.puppeteer_api_url = "http://localhost:3001/audit"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
        self.retry_attempts = 3
        self.retry_delay = 2  # seconds

    async def is_configured(self) -> bool:
        """Check if audit service can reach Puppeteer API"""
        try:
            # Test connection to Puppeteer API
            response = await self.client.get(f"{self.puppeteer_api_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Puppeteer API not reachable: {str(e)}")
            return False

    async def audit_website(self, url: str) -> AuditResponseModel:
        """
        Audit a website using the local Puppeteer API
        Returns structured audit data or error
        """
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        logger.info(f"Starting audit for: {url}")

        for attempt in range(self.retry_attempts):
            try:
                response = await self.client.post(
                    self.puppeteer_api_url,
                    json={"url": url},
                    timeout=httpx.Timeout(45.0, connect=10.0)
                )

                if response.status_code == 200:
                    data = response.json()

                    # Validate required fields
                    if 'success' not in data:
                        raise ValueError("Invalid response format: missing 'success' field")

                    if data['success']:
                        if 'data' not in data:
                            raise ValueError("Invalid response format: missing 'data' field")

                        audit_data = data['data']
                        required_fields = ['load_time', 'ssl', 'h1_count']
                        for field in required_fields:
                            if field not in audit_data:
                                raise ValueError(f"Invalid response format: missing '{field}' in data")

                    return AuditResponseModel(**data)

                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"Audit request failed (attempt {attempt + 1}/{self.retry_attempts}): {error_msg}")

            except httpx.ConnectError:
                error_msg = "Connection error - Puppeteer API may not be running"
                logger.warning(f"{error_msg} (attempt {attempt + 1}/{self.retry_attempts})")

            except httpx.TimeoutException:
                error_msg = "Request timed out"
                logger.warning(f"{error_msg} (attempt {attempt + 1}/{self.retry_attempts})")

            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"Unexpected error during audit (attempt {attempt + 1}/{self.retry_attempts}): {error_msg}")

            # Wait before retry (exponential backoff)
            if attempt < self.retry_attempts - 1:
                wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        # All attempts failed
        error_msg = f"Failed to audit {url} after {self.retry_attempts} attempts"
        logger.error(error_msg)
        return AuditResponseModel(
            success=False,
            error=error_msg,
            timestamp=datetime.utcnow()
        )

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global audit_service instance
audit_service = AuditService()