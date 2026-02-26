import asyncio
import logging
from typing import Optional
import httpx
from datetime import datetime

# Local imports
from ..database import database
from ..models import TelegramReportModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self):
        self.base_url = "https://api.telegram.org"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))

    async def is_configured(self) -> bool:
        """Check if Telegram service is properly configured"""
        try:
            settings = await database.get_settings()
            return bool(settings.telegram_bot_token and settings.telegram_chat_id)
        except Exception as e:
            logger.error(f"Error checking Telegram configuration: {str(e)}")
            return False

    async def send_message(self, message: str) -> bool:
        """
        Send a regular Telegram message
        Returns True if successful
        """
        if not await self.is_configured():
            logger.warning("Telegram not configured, cannot send message")
            return False

        try:
            settings = await database.get_settings()

            # Format message with timestamp
            full_message = f"{message}\n\n⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"

            api_url = f"{self.base_url}/bot{settings.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": settings.telegram_chat_id,
                "text": full_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }

            response = await self.client.post(api_url, json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info("Telegram message sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error response: {result}")
            else:
                logger.error(f"Telegram API request failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {str(e)}", exc_info=True)

        return False

    async def send_alert(self, message: str) -> bool:
        """
        Send an alert message with warning emoji
        Returns True if successful
        """
        if not message.startswith(("❌", "⚠️", "🚨")):
            message = f"⚠️ {message}"

        return await self.send_message(message)

    async def send_report(self, report_data: dict) -> bool:
        """
        Send formatted daily report
        Returns True if successful
        """
        try:
            # Build report message from data
            lines = ["📊 <b>Daily Report</b>"]

            if 'emails_sent' in report_data:
                lines.append(f"📬 Emails Sent: <b>{report_data['emails_sent']}</b>")

            if 'last_lead' in report_data:
                lines.append(f"📎 Last Lead: <b>ID {report_data['last_lead']}</b>")

            if 'current_target' in report_data:
                target = report_data['current_target']
                location = target['country']
                if target.get('state'):
                    location += f", {target['state']}"
                lines.append(f"🎯 Target: <b>{target['industry']}</b> in <b>{location}</b>")

            if 'inventory_count' in report_data:
                lines.append(f"📦 Inventory: <b>{report_data['inventory_count']}</b> leads")

            lines.append(f"\n⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

            report_message = "\n".join(lines)
            return await self.send_message(report_message)

        except Exception as e:
            logger.error(f"Failed to send Telegram report: {str(e)}", exc_info=True)
            return False

    async def test_connection(self) -> bool:
        """
        Test Telegram API connection
        Returns True if successful
        """
        if not await self.is_configured():
            return False

        try:
            settings = await database.get_settings()
            api_url = f"{self.base_url}/bot{settings.telegram_bot_token}/getMe"

            response = await self.client.get(api_url)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info("Telegram API connection test successful")
                    return True

            logger.error(f"Telegram API connection test failed: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Telegram API connection test error: {str(e)}", exc_info=True)
            return False

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global telegram_service instance
telegram_service = TelegramService()