import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.timezone = pytz.UTC

    async def start(self):
        if not self.scheduler.running:
            # Daily scheduled run at 8 AM UTC
            self.scheduler.add_job(
                self._scheduled_execution,
                trigger=CronTrigger(hour=8, minute=0, timezone=self.timezone),
                id="daily_engine",
                replace_existing=True
            )
            self.scheduler.start()
            logger.info("Scheduler started. Daily job scheduled at 8:00 AM UTC")
            
            # IMMEDIATE execution on startup for testing (remove in production)
            await self._scheduled_execution()

    async def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")

    async def _scheduled_execution(self):
        try:
            from .engine import engine
            logger.info("Running scheduled engine task...")
            result = await engine.run()
            logger.info(f"Engine task completed: {result}")
        except Exception as e:
            logger.error(f"Scheduler execution failed: {e}", exc_info=True)

scheduler = Scheduler()
