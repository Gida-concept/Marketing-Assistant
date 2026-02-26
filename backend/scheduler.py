import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time
import pytz
from contextlib import asynccontextmanager
from typing import Optional

# Local imports
from .engine import engine
from .database import database
from .models import EngineStateModel
from .services.telegram_service import telegram_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.timezone = pytz.timezone('UTC')  # Will be configurable via settings later
        self.job_id = "daily_agency_engine"

    def set_timezone(self, timezone_str: str = 'UTC'):
        """Set the scheduler timezone"""
        try:
            self.timezone = pytz.timezone(timezone_str)
        except Exception as e:
            logger.error(f"Invalid timezone {timezone_str}: {e}")
            self.timezone = pytz.utc

    async def start(self):
        """Start the scheduler and schedule the daily job"""
        if not self.scheduler.running:
            # Add cron job to run daily at 8:00 AM in specified timezone
            self.scheduler.add_job(
                self._scheduled_execution,
                trigger=CronTrigger(
                    hour=8,  # 8:00 AM daily
                    minute=0,
                    timezone=self.timezone
                ),
                id=self.job_id,
                replace_existing=True,
                misfire_grace_time=3600  # Allow up to 1 hour delay
            )

            self.scheduler.start()
            logger.info(f"Scheduler started. Daily job scheduled at 8:00 AM {self.timezone}")

            # Execute immediately if enabled (handles server restarts)
            await self._execute_if_enabled()

    async def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")

    async def _scheduled_execution(self):
        """Scheduled execution wrapper"""
        logger.info("Starting scheduled engine execution")
        await self._execute_if_enabled()

    async def _execute_if_enabled(self):
        """Execute engine if enabled and not already running"""
        try:
            # Get current engine state from database
            async for session in database.get_session():
                result = await session.execute("SELECT is_enabled FROM engine_state WHERE id = 1")
                row = result.fetchone()

                if row and row[0]:  # is_enabled == True
                    logger.info("Engine is enabled, starting execution...")
                    await engine.run()
                else:
                    logger.info("Engine is disabled, skipping execution")
                break

        except Exception as e:
            logger.error(f"Error checking engine state: {e}")
            # Ensure we don't block the scheduler on error
            pass

    async def trigger_manual_run(self):
        """Trigger a manual run of the engine"""
        logger.info("Manual engine execution triggered")
        await engine.run()

    async def set_schedule_time(self, hour: int, minute: int = 0):
        """Update the schedule time (24-hour format)"""
        if not (0 <= hour <= 23):
            raise ValueError("Hour must be between 0 and 23")
        if not (0 <= minute <= 59):
            raise ValueError("Minute must be between 0 and 59")

        # Update cron trigger
        self.scheduler.reschedule_job(
            self.job_id,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                timezone=self.timezone
            )
        )
        logger.info(f"Schedule updated to {hour:02d}:{minute:02d} {self.timezone}")


# Global scheduler instance
scheduler = Scheduler()


@asynccontextmanager
async def lifespan(app):
    """
    FastAPI lifespan handler for scheduler management
    Starts scheduler on startup, shuts down on shutdown
    """
    # Startup
    await database.init_db()  # Ensure DB is initialized
    await scheduler.start()

    yield  # Application runs here

    # Shutdown
    await scheduler.shutdown()