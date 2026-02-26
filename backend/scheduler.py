# backend/scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time
import pytz

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.timezone = pytz.timezone('UTC')
        self.job_id = "daily_agency_engine"
    
    async def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.add_job(
                self._scheduled_execution,
                trigger=CronTrigger(hour=8, minute=0, timezone=self.timezone),
                id=self.job_id,
                replace_existing=True,
                misfire_grace_time=3600
            )
            self.scheduler.start()
            logger.info(f"Scheduler started. Daily job scheduled at 8:00 AM {self.timezone}")
    
    async def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")
    
    async def _scheduled_execution(self):
        """Execute engine via direct import inside function to avoid circular import"""
        try:
            from backend.engine import engine
            logger.info("Running scheduled engine task...")
            await engine.run()
        except Exception as e:
            logger.error(f"Scheduler execution failed: {e}")

# Global scheduler instance
scheduler = Scheduler()
