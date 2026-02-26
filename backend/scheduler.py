import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.timezone = pytz.timezone('UTC')

    async def start(self):
        if not self.scheduler.running:
            self.scheduler.add_job(
                self._scheduled_execution,
                trigger=CronTrigger(hour=8, minute=0, timezone=self.timezone),
                id="daily_engine",
                replace_existing=True
            )
            self.scheduler.start()
            logger.info("Scheduler started")

    async def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")

    async def _scheduled_execution(self):
        try:
            from backend.engine import engine
            await engine.run()
        except Exception as e:
            logger.error(f"Job failed: {e}")

scheduler = Scheduler()
