# backend/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.timezone = pytz.UTC

    async def start(self):
        if not self.scheduler.running:
            self.scheduler.add_job(
                self._scheduled_execution,
                trigger=CronTrigger(hour=8, minute=0, timezone=self.timezone),
                id="daily_engine",
                replace_existing=True
            )
            self.scheduler.start()
            logger.info("Scheduler started.")

    async def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down.")

    async def _scheduled_execution(self):
        try:
            from .engine import engine
            await engine.run()
        except Exception as e:
            logger.error(f"Job execution failed: {e}")

scheduler = Scheduler()
