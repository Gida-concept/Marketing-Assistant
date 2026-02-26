import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime

# Local imports
from ..database import database
from ..models import ErrorResponseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SerpService:
    def __init__(self):
        self.base_url = "https://serpapi.com/search"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))

    async def is_configured(self) -> bool:
        """Check if SerpApi service is properly configured"""
        try:
            settings = await database.get_settings()
            return bool(settings.serp_api_key)
        except Exception as e:
            logger.error(f"Error checking SerpApi configuration: {str(e)}")
            return False

    async def search(self, query: str, pagination_start: int = 0) -> List[Dict[str, Any]]:
        """
        Perform Google search using SerpApi
        Returns list of lead data dictionaries
        """
        if not await self.is_configured():
            logger.error("SerpApi not configured")
            return []

        try:
            settings = await database.get_settings()

            # Build parameters for SerpApi
            params = {
                'api_key': settings.serp_api_key,
                'engine': 'google',
                'q': query,
                'start': pagination_start,
                'num': 10,  # Number of results per page
                'hl': 'en',
                'gl': 'us'
            }

            logger.info(f"Performing SERP search: {query} (page start: {pagination_start})")

            response = await self.client.get(self.base_url, params=params)

            if response.status_code != 200:
                logger.error(f"SerpApi request failed: {response.status_code} - {response.text}")
                return []

            data = response.json()

            # Extract organic results
            leads_data = []
            if 'organic_results' in data:
                for result in data['organic_results']:
                    title = result.get('title', '')
                    link = result.get('link', '')
                    snippet = result.get('snippet', '')

                    # Extract business name from title (remove common suffixes)
                    business_name = title
                    for suffix in [' - Google Search', ' | Site', ' | Website', ' Official Site']:
                        if business_name.endswith(suffix):
                            business_name = business_name[:-len(suffix)]
                            break

                    # Try to extract email from snippet using basic pattern
                    email = None
                    # This is a simple extraction - actual emails will be found in audit phase
                    if '@' in snippet:
                        words = snippet.split()
                        for word in words:
                            if '@' in word and '.' in word and word.index('@') > 0:
                                # Basic email validation
                                parts = word.strip('.,;:()[]{}"\'').split('@')
                                if len(parts) == 2 and len(parts[1].split('.')) >= 2:
                                    email = word.strip('.,;:()[]{}"\'')
                                    break

                    lead_data = {
                        'business_name': business_name,
                        'website': link,
                        'email': email,
                        'created_at': datetime.utcnow()
                    }
                    leads_data.append(lead_data)

            logger.info(f"SerpApi returned {len(leads_data)} results for query: {query}")
            return leads_data

        except httpx.TimeoutException:
            logger.error("SerpApi request timed out")
            return []
        except httpx.RequestError as e:
            logger.error(f"SerpApi request error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in SerpApi search: {str(e)}", exc_info=True)
            return []

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global serp_service instance
serp_service = SerpService()