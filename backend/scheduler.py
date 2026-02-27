# backend/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        # Use UTC timezone for consistency
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        # Define the cron trigger for daily execution at 8 AM UTC
        self.daily_trigger = CronTrigger(hour=8, minute=0, timezone=pytz.UTC)
        self.job_id = "daily_agency_engine"

    async def start(self):
        """Start the scheduler and add the daily job."""
        if not self.scheduler.running:
            # Add the job with the defined cron trigger
            self.scheduler.add_job(
                self._scheduled_execution,
                trigger=self.daily_trigger,
                id=self.job_id,
                replace_existing=True, # Replace if a job with the same ID already exists
                misfire_grace_time=3600 # Give 1 hour grace time for missed jobs
            )
            self.scheduler.start()
            logger.info(f"Scheduler started. Daily job '{self.job_id}' scheduled for 8:00 AM UTC.")

    async def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down.")

    async def _scheduled_execution(self):
        """Execute the engine task via import inside function to avoid circular import."""
        try:
            from backend.engine import engine
            logger.info("Running scheduled engine task...")
            await engine.run() # Execute the engine's run method
        except Exception as e:
            logger.error(f"Scheduler execution failed: {e}", exc_info=True) # Log the full traceback

# Create the global scheduler instance
scheduler = Scheduler()
