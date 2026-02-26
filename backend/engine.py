import asyncio
import logging
from datetime import datetime, timedelta
import httpx
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# Local imports
from .database import database
from .models import (
    LeadModel, ConfigModel, EngineStateModel, StatsModel,
    LeadStatus, ErrorResponseModel
)
from .services.serp_service import serp_service
from .services.audit_service import audit_service
from .services.groq_service import groq_service
from .services.email_service import email_service
from .services.telegram_service import telegram_service
from .services.inventory_service import inventory_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgencyEngine:
    def __init__(self):
        self.is_running = False
        self.execution_lock = asyncio.Lock()

    async def run(self):
        """Main engine execution method - entry point for daily processing"""
        if self.is_running:
            logger.warning("Engine is already running. Skipping execution.")
            return

        async with self.execution_lock:
            if self.is_running:
                return

            self.is_running = True
            logger.info("Starting agency engine execution")

            try:
                # Phase 0: Initial checks and setup
                if not await self._pre_execution_check():
                    logger.info("Pre-execution check failed or engine disabled. Exiting.")
                    return

                # Update engine state
                await self._update_engine_state(is_running=True)

                # Phase 1: Inventory Check
                await self._phase_inventory_check()

                # Phase 2: Scraping (if needed)
                if await self._needs_scraping():
                    await self._phase_scraping()

                # Phase 3: Audit
                await self._phase_audit()

                # Phase 4: 1-hour cooldown
                await self._phase_cooldown()

                # Phase 5: Persistent Outreach
                await self._phase_outreach()

                # Phase 6: Daily Report
                await self._phase_daily_report()

                logger.info("Agency engine execution completed successfully")

            except Exception as e:
                logger.error(f"Engine execution error: {str(e)}", exc_info=True)
                await telegram_service.send_alert(f"🚨 Engine Error: {str(e)}")

            finally:
                # Always update final state
                await self._update_engine_state(
                    is_running=False,
                    last_run_date=datetime.utcnow()
                )
                self.is_running = False

    async def _pre_execution_check(self) -> bool:
        """Check if engine should proceed with execution"""
        try:
            # Get engine state
            engine_state = await database.get_engine_state()
            if not engine_state.is_enabled:
                logger.info("Engine is not enabled. Skipping execution.")
                return False

            # Verify required services are available
            if not await serp_service.is_configured():
                error_msg = "SerpApi not configured"
                logger.error(error_msg)
                await telegram_service.send_alert(f"❌ {error_msg}")
                return False

            if not await groq_service.is_configured():
                error_msg = "Groq API not configured"
                logger.error(error_msg)
                await telegram_service.send_alert(f"❌ {error_msg}")
                return False

            if not await email_service.is_configured():
                error_msg = "SMTP not configured"
                logger.error(error_msg)
                await telegram_service.send_alert(f"❌ {error_msg}")
                return False

            return True

        except Exception as e:
            logger.error(f"Pre-execution check failed: {str(e)}")
            return False

    async def _phase_inventory_check(self):
        """Check current inventory levels against threshold"""
        try:
            audited_count = await inventory_service.get_audited_count()
            settings = await database.get_settings()

            if audited_count >= settings.inventory_threshold:
                message = f"📦 Inventory full ({audited_count}/{settings.inventory_threshold}). Resuming outreach."
                logger.info(message)
                await telegram_service.send_message(message)
            else:
                message = f"📉 Low inventory ({audited_count}/{settings.inventory_threshold}). Proceeding with scraping."
                logger.info(message)
                await telegram_service.send_message(message)

        except Exception as e:
            logger.error(f"Inventory check phase error: {str(e)}")
            await telegram_service.send_alert(f"⚠️ Inventory Check Error: {str(e)}")

    async def _needs_scraping(self) -> bool:
        """Determine if scraping phase is needed"""
        try:
            audited_count = await inventory_service.get_audited_count()
            settings = await database.get_settings()
            return audited_count < settings.inventory_threshold

        except Exception as e:
            logger.error(f"Error determining scraping need: {str(e)}")
            # Default to scraping if we can't determine status
            return True

    async def _phase_scraping(self):
        """Execute systematic scraping using SerpApi"""
        logger.info("Starting scraping phase")

        try:
            settings = await database.get_settings()
            config = await database.get_config()

            # Track how many SERP queries we've made today
            serp_queries_used = 0

            while serp_queries_used < settings.daily_serp_limit:
                # Get next target based on current indices
                target = await inventory_service.get_next_target(
                    config.industry_idx,
                    config.location_idx,
                    config.state_idx
                )

                if not target:
                    logger.info("No more targets available. Resetting indices.")
                    # Reset all indices and start over
                    await database.reset_target_indices()
                    continue

                # Perform SERP search for this target
                search_query = f"{target.industry} in {target.country}"
                if target.state:
                    search_query += f", {target.state}"

                leads_data = await serp_service.search(
                    query=search_query,
                    pagination_start=config.pagination_start
                )

                if not leads_data:
                    logger.info(f"No results for {search_query}. Moving to next target.")
                    # Move to next target
                    await database.increment_target_indices(
                        current_industry_idx=config.industry_idx,
                        current_location_idx=config.location_idx,
                        current_state_idx=config.state_idx,
                        target=target
                    )
                    # Reset pagination
                    config.pagination_start = 0
                    await database.update_config(config)
                    continue

                # Save scraped leads
                for lead_data in leads_data:
                    lead_data['industry'] = target.industry
                    lead_data['country'] = target.country
                    lead_data['state'] = target.state
                    lead_data['status'] = LeadStatus.SCRAPED

                    await database.create_lead(lead_data)

                # Update configuration for next iteration
                new_pagination = config.pagination_start + len(leads_data)
                if new_pagination >= 100:  # Typical SERP pagination limit
                    # Move to next target
                    await database.increment_target_indices(
                        current_industry_idx=config.industry_idx,
                        current_location_idx=config.location_idx,
                        current_state_idx=config.state_idx,
                        target=target
                    )
                    config.pagination_start = 0
                else:
                    config.pagination_start = new_pagination

                await database.update_config(config)
                serp_queries_used += 1

                # Small delay between queries to be respectful
                await asyncio.sleep(1)

            logger.info(f"Scraping phase completed. Used {serp_queries_used} SERP queries.")

        except Exception as e:
            logger.error(f"Scraping phase error: {str(e)}", exc_info=True)
            await telegram_service.send_alert(f"❌ Scraping Error: {str(e)}")

    async def _phase_audit(self):
        """Audit newly scraped leads using Puppeteer API"""
        logger.info("Starting audit phase")

        try:
            # Get all SCRAPED leads that don't have websites or need auditing
            scraped_leads = await database.get_leads_by_status(LeadStatus.SCRAPED)

            processed_count = 0
            for lead in scraped_leads:
                if not lead.website:
                    # No website to audit, mark as AUDITED with low priority
                    await database.update_lead(
                        lead.id,
                        LeadModel(
                            id=lead.id,
                            priority_score=1,
                            audit_notes="No website available",
                            status=LeadStatus.AUDITED
                        )
                    )
                    processed_count += 1
                    continue

                # Audit via Puppeteer API
                audit_result = await audit_service.audit_website(str(lead.website))

                if audit_result.success and audit_result.data:
                    data = audit_result.data
                    priority_score = 0
                    notes_parts = []

                    # Calculate priority score and generate notes
                    if not data.get('ssl', True):
                        priority_score += 2
                        notes_parts.append("No SSL certificate")

                    load_time = data.get('load_time')
                    if load_time and load_time > 4.0:
                        priority_score += 2
                        notes_parts.append(f"Slow load time ({load_time}s)")

                    h1_count = data.get('h1_count', 0)
                    if h1_count == 0:
                        priority_score += 1
                        notes_parts.append("No H1 tags found")

                    emails = data.get('emails', [])
                    if emails:
                        # Use first email found
                        await database.update_lead(
                            lead.id,
                            LeadModel(
                                id=lead.id,
                                email=emails[0],
                                load_time=load_time,
                                ssl_status=data.get('ssl'),
                                h1_count=h1_count,
                                priority_score=priority_score,
                                audit_notes="; ".join(notes_parts) if notes_parts else "Website audited",
                                status=LeadStatus.AUDITED
                            )
                        )
                    else:
                        await database.update_lead(
                            lead.id,
                            LeadModel(
                                id=lead.id,
                                load_time=load_time,
                                ssl_status=data.get('ssl'),
                                h1_count=h1_count,
                                priority_score=priority_score,
                                audit_notes="; ".join(
                                    notes_parts) if notes_parts else "Website audited, no emails found",
                                status=LeadStatus.AUDITED
                            )
                        )

                    processed_count += 1

                    # Respectful delay between audits
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"Audit failed for {lead.website}: {audit_result.error}")
                    # Still mark as audited to prevent retry loops
                    await database.update_lead(
                        lead.id,
                        LeadModel(
                            id=lead.id,
                            audit_notes=f"Audit failed: {audit_result.error}",
                            status=LeadStatus.AUDITED
                        )
                    )
                    processed_count += 1

            logger.info(f"Audit phase completed. Processed {processed_count} leads.")

        except Exception as e:
            logger.error(f"Audit phase error: {str(e)}", exc_info=True)
            await telegram_service.send_alert(f"❌ Audit Error: {str(e)}")

    async def _phase_cooldown(self):
        """One hour cooldown period before outreach"""
        logger.info("Starting 1-hour cooldown period")
        await telegram_service.send_message("⏳ Starting 1-hour cooldown before outreach begins...")

        # Send progress updates during cooldown
        for i in range(6):
            await asyncio.sleep(600)  # Sleep 10 minutes
            remaining = 60 - ((i + 1) * 10)
            if remaining > 0:
                await telegram_service.send_message(f"⏰ {remaining} minutes remaining in cooldown...")

        logger.info("Cooldown period completed")

    async def _phase_outreach(self):
        """Execute persistent outreach with Groq personalization and SMTP sending"""
        logger.info("Starting outreach phase")

        try:
            settings = await database.get_settings()
            config = await database.get_config()
            stats = await database.get_stats()

            # Calculate remaining emails allowed today
            emails_remaining = max(0, settings.daily_email_limit - stats.emails_sent_today)
            if emails_remaining == 0:
                logger.info("Daily email limit reached. Skipping outreach.")
                await telegram_service.send_message("🎯 Daily email limit reached. No outreach performed.")
                return

            # Get leads to email (AUDITED leads after last_emailed_lead_id)
            leads_to_email = await database.get_leads_for_outreach(
                last_emailed_id=config.last_emailed_lead_id,
                limit=min(emails_remaining, settings.daily_email_limit)
            )

            if not leads_to_email:
                logger.info("No leads available for outreach.")
                await telegram_service.send_message("📭 No leads available for outreach.")
                return

            logger.info(f"Processing {len(leads_to_email)} leads for outreach")
            successful_sends = 0

            for lead in leads_to_email:
                try:
                    # Generate personalized opening line
                    personalization_result = await groq_service.generate_personalization(
                        audit_notes=lead.audit_notes or ""
                    )

                    opening_line = "Hi there,"
                    if personalization_result.success and personalization_result.opening_line:
                        opening_line = personalization_result.opening_line
                    else:
                        logger.warning(f"Personalization failed for lead {lead.id}: {personalization_result.error}")

                    # Send email
                    send_result = await email_service.send_outreach_email(
                        lead=lead,
                        opening_line=opening_line
                    )

                    if send_result.success:
                        # Update lead status
                        await database.update_lead(
                            lead.id,
                            LeadModel(
                                id=lead.id,
                                status=LeadStatus.EMAILED
                            )
                        )

                        # Update config last_emailed_lead_id
                        config.last_emailed_lead_id = lead.id
                        await database.update_config(config)

                        # Update stats
                        stats.emails_sent_today += 1
                        stats.last_email_date = datetime.utcnow()
                        await database.update_stats(stats)

                        successful_sends += 1

                        logger.info(f"Email sent successfully to {lead.business_name} (ID: {lead.id})")

                        # Wait 10 minutes between sends (as specified)
                        if successful_sends < len(leads_to_email):  # Don't wait after the last one
                            logger.info("Waiting 10 minutes before next email...")
                            await telegram_service.send_message(
                                f"📨 Email {successful_sends}/{len(leads_to_email)} sent. Waiting 10 minutes...")
                            await asyncio.sleep(600)
                    else:
                        logger.error(f"Failed to send email to {lead.business_name}: {send_result.message}")
                        await telegram_service.send_alert(f"⚠️ Email Failed: {send_result.message}")

                        # Continue with next lead (don't block entire process)
                        continue

                except Exception as e:
                    logger.error(f"Error processing lead {lead.id}: {str(e)}", exc_info=True)
                    await telegram_service.send_alert(f"⚠️ Lead Processing Error: ID {lead.id} - {str(e)}")
                    continue

            logger.info(f"Outreach phase completed. Successfully sent {successful_sends} emails.")
            await telegram_service.send_message(
                f"✅ Outreach completed. {successful_sends}/{len(leads_to_email)} emails sent successfully.")

        except Exception as e:
            logger.error(f"Outreach phase error: {str(e)}", exc_info=True)
            await telegram_service.send_alert(f"❌ Outreach Error: {str(e)}")

    async def _phase_daily_report(self):
        """Send comprehensive daily report via Telegram"""
        logger.info("Generating daily report")

        try:
            stats = await database.get_stats()
            config = await database.get_config()
            settings = await database.get_settings()

            # Get current target
            current_target = await inventory_service.get_current_target(
                config.industry_idx,
                config.location_idx,
                config.state_idx
            )

            # Get inventory counts
            total_audited = await inventory_service.get_audited_count()
            emailed_count = await inventory_service.get_emailed_count()
            scraped_count = await inventory_service.get_scraped_count()

            # Format report
            report_lines = [
                "📊 <b>Daily Report</b>",
                f"📬 Emails Sent Today: <b>{stats.emails_sent_today}</b>",
                f"📅 Last Email: {stats.last_email_date.strftime('%H:%M') if stats.last_email_date else 'Never'}",
            ]

            if config.last_emailed_lead_id > 0:
                report_lines.append(f"📎 Last Lead Emailed: ID <b>{config.last_emailed_lead_id}</b>")

            if current_target:
                location = current_target.country
                if current_target.state:
                    location += f", {current_target.state}"
                report_lines.append(f"🎯 Current Target: <b>{current_target.industry}</b> in <b>{location}</b>")

            report_lines.extend([
                f"📦 Remaining Inventory: <b>{total_audited}</b> audited leads",
                "",
                "📋 <b>Inventory Breakdown</b>",
                f"• Scraped: {scraped_count}",
                f"• Audited: {total_audited}",
                f"• Emailed: {emailed_count}",
                "",
                f"⚙️ Daily Limits: {stats.emails_sent_today}/{settings.daily_email_limit} emails used"
            ])

            report_message = "\n".join(report_lines)
            await telegram_service.send_message(report_message)
            logger.info("Daily report sent successfully")

        except Exception as e:
            logger.error(f"Daily report phase error: {str(e)}", exc_info=True)
            await telegram_service.send_alert(f"❌ Daily Report Error: {str(e)}")


# Global engine instance
engine = AgencyEngine()