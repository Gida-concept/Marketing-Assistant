import httpx
import asyncio
import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class Engine:
    def __init__(self):
        self.is_running = False # Internal flag for this instance
        self.serp_base_url = "https://serpapi.com/search"
        self.skip_patterns = [
            r'builtin\.com', r'builtinsf\.com', r'thegoodtrade\.com',
            r'toddshelton\.com', r'directory', r'listings?', r'blog',
            r'/blog/', r'/features/', r'/companies/', r'fashion-companies',
            r'wikipedia', r'crunchbase', r'glassdoor', r'yelp\.com'
        ]

    async def run(self):
        # Prevent concurrent runs of this instance
        if self.is_running:
            logger.warning("Engine.run() called while already running on this instance. Skipping.")
            return {"success": False, "message": "Engine already running on this instance"}

        self.is_running = True
        try:
            # Update database state to RUNNING
            await database.update_engine_state(is_running=True)
            logger.info("=" * 60)
            logger.info("🚀 ENGINE EXECUTION STARTED")
            logger.info("=" * 60)

            settings = await database.get_settings()
            config = await database.get_config()
            stats = await database.get_stats()

            if not settings or not settings.serp_api_key:
                logger.error("❌ SerpApi key not configured")
                return {"success": False, "message": "SerpApi key not configured"}

            if stats.emails_sent_today >= settings.daily_email_limit:
                logger.warning(f"⚠️ Daily email limit ({settings.daily_email_limit}) reached. Skipping email phase.")

            targets = await database.get_all_targets()
            if not targets:
                logger.error("❌ No targets configured")
                return {"success": False, "message": "No targets configured"}

            target = await database.get_target_by_indices(config.industry_idx, config.location_idx)
            logger.info(f"🎯 Target: {target.industry} in {target.state or 'N/A'}, {target.country}")

            audited_count = await database.count_leads_by_status("AUDITED")
            logger.info(f"📊 Current audited leads: {audited_count} (threshold: {settings.inventory_threshold})")

            if audited_count < settings.inventory_threshold:
                logger.info("🔍 Inventory below threshold - starting lead scraping...")
                result = await self.scrape_leads(target, settings)
                if not result["success"]:
                    logger.error(f"❌ Scraping failed: {result['message']}")
                    return result
                logger.info("✅ Scraping completed successfully")
            else:
                logger.info("✅ Inventory sufficient - skipping scraping phase")

            # Update config for next cycle
            await database.update_config(
                industry_idx=(config.industry_idx + 1) % len(targets),
                location_idx=config.location_idx
            )

            # Update database state's last run date
            await database.update_engine_state(last_run_date=datetime.utcnow())

            logger.info("=" * 60)
            logger.info("✅ ENGINE EXECUTION COMPLETED")
            logger.info("=" * 60)
            return {"success": True, "message": f"Engine cycle completed for {target.industry} in {target.country}"}

        except Exception as e:
            import traceback
            logger.error(f"💥 Engine crash: {e}\n{traceback.format_exc()}")
            return {"success": False, "message": f"Engine error: {str(e)}"}
        finally:
            # Reset internal flag and database state
            self.is_running = False
            await database.update_engine_state(is_running=False)

    async def scrape_leads(self, target, settings):
        # Build location string
        location_parts = []
        if target.state and target.state.strip():
            location_parts.append(target.state.strip())
        if target.country and target.country.strip():
            location_parts.append(target.country.strip())
        location_query = ", ".join(location_parts) if location_parts else None

        query = f"{target.industry} company"
        logger.info(f"\n🔍 STEP 1: Google Maps Search")
        logger.info(f"   Query: '{query}'")
        logger.info(f"   Location: '{location_query or 'Global (no location filter)'}'")
        logger.info(f"   Raw State: '{target.state or 'None'}'")
        logger.info(f"   Raw Country: '{target.country or 'None'}'")

        # Build base params
        params = {
            "engine": "google_maps",
            "q": query,
            "api_key": settings.serp_api_key,
            "type": "search",
            "google_domain": "google.com",
            "hl": "en",
            "gl": "us"
        }

        # Only add location if we have one
        if location_query:
            params["location"] = location_query

        # Initialize 'data' variable at function scope
        data = None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # First attempt with location parameter (if provided)
                try:
                    serp_resp = await client.get(self.serp_base_url, params=params)
                    serp_resp.raise_for_status()
                    data = serp_resp.json() # Assign to the function-scoped 'data'
                    logger.info("✅ Location-based search successful")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 400:
                        logger.warning("⚠️ SerpApi returned 400 Bad Request (invalid/unrecognized location)")
                        logger.warning("   Attempting fallback with broader search (no location parameter)...")

                        # Remove location parameter for global/broader search
                        params.pop("location", None)
                        serp_resp = await client.get(self.serp_base_url, params=params)
                        serp_resp.raise_for_status()
                        data = serp_resp.json() # Assign to the function-scoped 'data'
                        logger.info("✅ Fallback search successful (global results)")
                    else:
                        raise

                # Ensure 'data' is defined before accessing
                if data is None:
                    logger.error("❌ SerpApi returned no data.")
                    return {"success": False, "message": "SerpApi returned no data"}

                # Now data is guaranteed to be defined and non-None
                results = data.get("local_results", [])
                logger.info(f"\n✅ STEP 2: Search Results")
                logger.info(f"   Total businesses found: {len(results)}")

                if not results:
                    logger.warning("⚠️ No businesses found in search results")
                    return {"success": False, "message": "No businesses found for this target"}

                scraped = 0
                processed_websites = set() # Track websites processed in this cycle to avoid re-processing duplicates from the same search

                # Loop through results
                for idx, result in enumerate(results[:10], 1):
                    business_name = result.get("title", "").strip()
                    website = result.get("website", "").strip()
                    address = result.get("address", "")
                    phone = result.get("phone", "")
                    rating = result.get("rating", 0)
                    reviews = result.get("reviews", 0)

                    if not business_name or len(business_name) < 3:
                        logger.debug(f"   [#{idx}] Skipped (invalid name): {business_name}")
                        continue

                    # Skip if no website or already processed in this cycle
                    if not website or website in processed_websites:
                         if not website:
                             logger.debug(f"   [#{idx}] Skipped (no website): {business_name}")
                         else:
                             logger.debug(f"   [#{idx}] Skipped (duplicate in cycle): {website}")
                         continue

                    # Check if lead with this website already exists in the database
                    existing_lead = await database.get_lead_by_website(website)
                    if existing_lead:
                        logger.info(f"   [#{idx}] Skipped (already exists in DB): {website}")
                        processed_websites.add(website)
                        continue # Skip saving this lead

                    # Add to processed set for this cycle
                    processed_websites.add(website)

                    if website and self._should_skip_url(website, business_name):
                        logger.debug(f"   [#{idx}] Skipped (non-business URL): {business_name} | {website}")
                        continue

                    lead_id = await database.save_lead({
                        "business_name": business_name[:250],
                        "industry": target.industry[:100],
                        "country": target.country[:100],
                        "state": (target.state or "")[:100],
                        "website": website[:255] if website else None,
                        "email": None,
                        "load_time": None,
                        "ssl_status": None,
                        "h1_count": 0,
                        "priority_score": 30,
                        "status": "SCRAPED",
                        "audit_notes": f"Address: {address}, Phone: {phone}, Rating: {rating} ({reviews} reviews)"
                    })
                    scraped += 1

                    logger.info(f"\n✅ STEP 3: Lead #{scraped} Saved")
                    logger.info(f"   ID: {lead_id}")
                    logger.info(f"   Business: {business_name}")
                    logger.info(f"   Website: {website or 'No website'}")
                    logger.info(f"   Address: {address}")
                    logger.info(f"   Phone: {phone}")
                    logger.info(f"   Rating: {rating} ({reviews} reviews)")
                    logger.info(f"   Status: SCRAPED (no email yet)")

                    if website:
                        logger.info(f"\n🔍 STEP 4: Auditing Website (Lead #{scraped})")
                        logger.info(f"   URL: {website}")

                        try:
                            audit_resp = await client.post(
                                "http://localhost:3001/audit",
                                json={"url": website},
                                timeout=20
                            )
                            audit_resp.raise_for_status()
                            audit_data = audit_resp.json()

                            if audit_data.get("success"):
                                ad = audit_data["data"]
                                emails = ad.get("emails", [])
                                has_email = bool(emails and emails[0])

                                update_data = {
                                    "load_time": ad.get("load_time"),
                                    "ssl_status": ad.get("ssl"),
                                    "h1_count": ad.get("h1_count", 0),
                                    "priority_score": self.calculate_priority(ad),
                                    "audit_notes": f"SSL: {ad.get('ssl')}, Load: {ad.get('load_time', 0):.2f}s, H1s: {ad.get('h1_count', 0)}, Emails found: {len(emails)}"
                                }

                                if has_email:
                                    update_data["email"] = emails[0][:255]
                                    update_data["status"] = "AUDITED"
                                    logger.info(f"✅ STEP 5: Email Found (Lead #{scraped})")
                                    logger.info(f"   Email: {emails[0]}")
                                    logger.info(f"   SSL: {'✅ Yes' if ad.get('ssl') else '❌ No'}")
                                    logger.info(f"   Load Time: {ad.get('load_time', 0):.2f}s")
                                    logger.info(f"   H1 Tags: {ad.get('h1_count', 0)}")
                                    logger.info(f"   Status: AUDITED ✅")
                                else:
                                    logger.warning(f"⚠️ STEP 5: No Email Found (Lead #{scraped})")
                                    logger.info(f"   SSL: {'✅ Yes' if ad.get('ssl') else '❌ No'}")
                                    logger.info(f"   Load Time: {ad.get('load_time', 0):.2f}s")
                                    logger.info(f"   H1 Tags: {ad.get('h1_count', 0)}")
                                    logger.info(f"   Status: SCRAPED (no email)")

                                await database.update_lead(lead_id, update_data)
                            else:
                                logger.warning(f"⚠️ Audit API returned failure for {website}")

                        except Exception as e:
                            error_detail = str(e)
                            if "timeout" in error_detail.lower():
                                error_detail = "Timeout (site too slow)"
                            elif "connect" in error_detail.lower():
                                error_detail = "Connection failed"
                            logger.warning(f"⚠️ Audit failed for {business_name} ({website}): {error_detail}")

                    if scraped >= 5:
                        logger.info(f"\n✅ Reached target of {scraped} leads. Stopping scraping.")
                        break

                logger.info(f"\n✅ FINAL SUMMARY")
                logger.info(f"   Total leads scraped: {scraped}")
                logger.info(f"   Status: All saved as SCRAPED (email extraction attempted where website available)")
                return {"success": True, "message": f"Scraped {scraped} business leads from Google Maps"}

        except Exception as e:
            logger.error(f"❌ SerpApi error: {e}")
            return {"success": False, "message": f"SerpApi failed: {str(e)}"}

    def _should_skip_url(self, url, title):
        """Skip non-business URLs"""
        if not url:
            return False

        url_lower = url.lower()
        title_lower = title.lower() if title else ""

        # Skip social media/profile sites
        social_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com/in/', 'pinterest.com', 'wikipedia.org']
        for domain in social_domains:
            if domain in url_lower:
                return True

        # Skip directories/aggregators
        for pattern in self.skip_patterns:
            if re.search(pattern, url_lower) or re.search(pattern, title_lower):
                return True

        # Skip non-commercial TLDs in business context
        non_business_tlds = ['.edu', '.gov', '.org/wiki']
        for tld in non_business_tlds:
            if tld in url_lower:
                return True

        return False

    def calculate_priority(self, audit_data):
        score = 50
        if audit_data.get("ssl"):
            score += 20
        if audit_data.get("load_time", 999) < 3.0:
            score += 20
        if audit_data.get("h1_count", 0) > 0:
            score += 10
        return min(100, max(0, score))

    async def start(self):
        # Only update the enabled flag in the database
        await database.update_engine_state(is_enabled=True)
        return {"success": True, "message": "Engine enabled"}

    async def stop(self):
        # Only update the enabled flag in the database
        await database.update_engine_state(is_enabled=False)
        return {"success": True, "message": "Engine disabled"}

# Import database AFTER class definition to avoid circular import
# Assume 'database' and 'datetime' are available in the scope where Engine is instantiated
# You might need to pass the database instance or import it differently depending on your structure
# For now, assuming it's imported globally within this module or handled by the caller
from .database import database
from datetime import datetime # Import datetime for updating last_run_date

engine = Engine()
