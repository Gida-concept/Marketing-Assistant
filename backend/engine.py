import httpx
import asyncio
import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class Engine:
    def __init__(self):
        self.is_running = False
        self.serp_base_url = "https://serpapi.com/search"
        self.skip_patterns = [
            r'builtin\.com', r'builtinsf\.com', r'thegoodtrade\.com',
            r'toddshelton\.com', r'directory', r'listings?', r'blog',
            r'/blog/', r'/features/', r'/companies/', r'fashion-companies',
            r'wikipedia', r'crunchbase', r'glassdoor', r'yelp\.com'
        ]
        # Common location typo corrections
        self.location_corrections = {
            "carlifonia": "California",
            "califronia": "California",
            "califonia": "California",
            "newyork": "New York",
            "new york city": "New York",
            "ny": "New York",
            "texas": "Texas",
            "florida": "Florida",
            "illinois": "Illinois",
            "united states": "United States",
            "usa": "United States",
            "uk": "United Kingdom",
            "great britain": "United Kingdom"
        }
    
    async def run(self):
        if self.is_running:
            return {"success": False, "message": "Engine already running"}
        
        self.is_running = True
        try:
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
            
            await database.update_config(
                industry_idx=(config.industry_idx + 1) % len(targets),
                location_idx=config.location_idx
            )
            
            logger.info("=" * 60)
            logger.info("✅ ENGINE EXECUTION COMPLETED")
            logger.info("=" * 60)
            return {"success": True, "message": f"Engine cycle completed for {target.industry} in {target.country}"}
        
        except Exception as e:
            import traceback
            logger.error(f"💥 Engine crash: {e}\n{traceback.format_exc()}")
            return {"success": False, "message": f"Engine error: {str(e)}"}
        finally:
            self.is_running = False
    
    async def scrape_leads(self, target, settings):
        # Auto-correct location typos
        state_raw = (target.state or "").strip()
        country_raw = (target.country or "").strip()
        
        state_corrected = self._correct_location(state_raw)
        country_corrected = self._correct_location(country_raw)
        
        location_parts = []
        if state_corrected:
            location_parts.append(state_corrected)
        if country_corrected:
            location_parts.append(country_corrected)
        location_query = ", ".join(location_parts) if location_parts else "United States"
        
        query = f"{target.industry} company"
        logger.info(f"\n🔍 STEP 1: Google Maps Search")
        logger.info(f"   Query: '{query}'")
        logger.info(f"   Location: '{location_query}'")
        logger.info(f"   Raw State: '{state_raw}' → Corrected: '{state_corrected}'")
        logger.info(f"   Raw Country: '{country_raw}' → Corrected: '{country_corrected}'")
        
        params = {
            "engine": "google_maps",
            "q": query,
            "api_key": settings.serp_api_key,
            "type": "search",
            "location": location_query,
            "google_domain": "google.com",
            "hl": "en",
            "gl": "us"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # ✅ FIX: Proper variable scoping - define data AFTER successful request
                serp_resp = None
                data = None
                
                # First attempt with location parameter
                try:
                    serp_resp = await client.get(self.serp_base_url, params=params)
                    serp_resp.raise_for_status()
                    data = serp_resp.json()
                    logger.info("✅ Location-based search successful")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 400:
                        logger.warning("⚠️ SerpApi returned 400 Bad Request (invalid location)")
                        logger.warning("   Attempting fallback with broader search (no location parameter)...")
                        
                        # Fallback: Remove location parameter
                        params.pop("location", None)
                        serp_resp = await client.get(self.serp_base_url, params=params)
                        serp_resp.raise_for_status()
                        data = serp_resp.json()
                        logger.info("✅ Fallback search successful")
                    else:
                        raise
                
                # ✅ CRITICAL FIX: data is now guaranteed to be defined here
                results = data.get("local_results", []) if data else []
                logger.info(f"\n✅ STEP 2: Search Results")
                logger.info(f"   Total businesses found: {len(results)}")
                
                if not results:
                    logger.warning("⚠️ No businesses found in search results")
                    return {"success": False, "message": "No businesses found for this target"}
                
                scraped = 0
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
                    
                    if website and self._should_skip_url(website, business_name):
                        logger.debug(f"   [#{idx}] Skipped (non-business URL): {business_name} | {website}")
                        continue
                    
                    lead_id = await database.save_lead({
                        "business_name": business_name[:250],
                        "industry": target.industry[:100],
                        "country": country_corrected[:100],
                        "state": state_corrected[:100],
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
    
    def _correct_location(self, location: str) -> str:
        """Auto-correct common location typos"""
        if not location:
            return location
        
        location_lower = location.lower().strip()
        
        for typo, correction in self.location_corrections.items():
            if location_lower == typo.lower():
                logger.debug(f"   Auto-corrected location: '{location}' → '{correction}'")
                return correction
        
        for typo, correction in self.location_corrections.items():
            if typo.lower() in location_lower:
                corrected = location.replace(typo, correction, 1)
                logger.debug(f"   Auto-corrected location: '{location}' → '{corrected}'")
                return corrected
        
        return location
    
    def _should_skip_url(self, url, title):
        """Skip non-business URLs"""
        if not url:
            return False
        
        url_lower = url.lower()
        title_lower = title.lower() if title else ""
        
        social_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com/in/', 'pinterest.com', 'wikipedia.org']
        for domain in social_domains:
            if domain in url_lower:
                return True
        
        for pattern in self.skip_patterns:
            if re.search(pattern, url_lower) or re.search(pattern, title_lower):
                return True
        
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
        await database.update_engine_state(is_enabled=True)
        return {"success": True, "message": "Engine enabled"}
    
    async def stop(self):
        await database.update_engine_state(is_enabled=False)
        return {"success": True, "message": "Engine disabled"}

# Import database AFTER class definition to avoid circular import
from .database import database

engine = Engine()
