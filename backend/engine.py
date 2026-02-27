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
    
    async def run(self):
        if self.is_running:
            return {"success": False, "message": "Engine already running"}
        
        self.is_running = True
        try:
            settings = await database.get_settings()
            config = await database.get_config()
            stats = await database.get_stats()
            
            if not settings or not settings.serp_api_key:
                return {"success": False, "message": "SerpApi key not configured"}
            
            if stats.emails_sent_today >= settings.daily_email_limit:
                return {"success": False, "message": f"Daily email limit ({settings.daily_email_limit}) reached"}
            
            targets = await database.get_all_targets()
            if not targets:
                return {"success": False, "message": "No targets configured"}
            
            target = await database.get_target_by_indices(config.industry_idx, config.location_idx)
            audited_count = await database.count_leads_by_status("AUDITED")
            
            if audited_count < settings.inventory_threshold:
                result = await self.scrape_leads(target, settings)
                if not result["success"]:
                    return result
            
            await database.update_config(
                industry_idx=(config.industry_idx + 1) % len(targets),
                location_idx=config.location_idx
            )
            
            return {"success": True, "message": f"Engine cycle completed for {target.industry} in {target.country}"}
        
        except Exception as e:
            import traceback
            logger.error(f"Engine crash: {e}\n{traceback.format_exc()}")
            return {"success": False, "message": f"Engine error: {str(e)}"}
        finally:
            self.is_running = False
    
    async def scrape_leads(self, target, settings):
        # Build location string from target (supports international formats)
        location_parts = []
        if target.state:
            location_parts.append(target.state.strip())
        if target.country:
            location_parts.append(target.country.strip())
        location_query = ", ".join(location_parts) if location_parts else "United States"
        
        # Build Google Maps query
        query = f"{target.industry} company"
        
        # ✅ FIX: Use human-readable location parameter (no hardcoded coords)
        # SerpApi handles geocoding internally for 200+ countries
        params = {
            "engine": "google_maps",
            "q": query,
            "api_key": settings.serp_api_key,
            "type": "search",
            "location": location_query,  # ✅ International support (e.g., "London, UK", "Paris, France")
            "google_domain": "google.com",
            "hl": "en",
            "gl": "us"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                serp_resp = await client.get(self.serp_base_url, params=params)
                serp_resp.raise_for_status()
                data = serp_resp.json()
                
                # Google Maps returns "local_results" with business data
                results = data.get("local_results", [])
                logger.info(f"Google Maps returned {len(results)} businesses for '{query}' in {location_query}")
                
                if not results:
                    # Fallback: Try without location parameter (broader search)
                    logger.warning(f"No results for location '{location_query}', trying broader search")
                    params.pop("location", None)
                    serp_resp = await client.get(self.serp_base_url, params=params)
                    data = serp_resp.json()
                    results = data.get("local_results", [])
                    logger.info(f"Broad search returned {len(results)} businesses")
                
                scraped = 0
                for result in results[:15]:
                    business_name = result.get("title", "").strip()
                    website = result.get("website", "").strip()
                    address = result.get("address", "")
                    phone = result.get("phone", "")
                    rating = result.get("rating", 0)
                    reviews = result.get("reviews", 0)
                    
                    # Skip invalid entries
                    if not business_name or len(business_name) < 3:
                        continue
                    
                    # Skip non-business URLs BEFORE saving
                    if website and self._should_skip_url(website, business_name):
                        logger.debug(f"Skipped non-business URL: {business_name} | {website}")
                        continue
                    
                    # ✅ ALWAYS save lead as SCRAPED status (even without email/website)
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
                    logger.info(f"✅ SCRAPED: {business_name} | {website or 'No website'} | Location: {location_query}")
                    
                    # Audit website if available
                    if website:
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
                                
                                # Update lead with audit results
                                update_data = {
                                    "load_time": ad.get("load_time"),
                                    "ssl_status": ad.get("ssl"),
                                    "h1_count": ad.get("h1_count", 0),
                                    "priority_score": self.calculate_priority(ad),
                                    "audit_notes": f"SSL: {ad.get('ssl')}, Load: {ad.get('load_time', 0):.2f}s, H1s: {ad.get('h1_count', 0)}, Emails found: {len(emails)}"
                                }
                                
                                if emails and emails[0]:
                                    update_data["email"] = emails[0][:255]
                                    update_data["status"] = "AUDITED"
                                    logger.info(f"📧 AUDITED (+email): {business_name} | {emails[0]}")
                                else:
                                    logger.warning(f"⚠️ No email found on {website} (kept as SCRAPED)")
                                
                                await database.update_lead(lead_id, update_data)
                            
                        except Exception as e:
                            error_detail = str(e)
                            if "timeout" in error_detail.lower():
                                error_detail = "Timeout"
                            elif "connect" in error_detail.lower():
                                error_detail = "Connection failed"
                            logger.warning(f"⚠️ Audit failed for {business_name} ({website}): {error_detail}")
                    
                    if scraped >= 10:
                        break
                
                logger.info(f"✅ Scraping completed: {scraped} leads saved from Google Maps")
                return {"success": True, "message": f"Scraped {scraped} business leads"}
        
        except Exception as e:
            logger.error(f"SerpApi error: {e}")
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
        await database.update_engine_state(is_enabled=True)
        return {"success": True, "message": "Engine enabled"}
    
    async def stop(self):
        await database.update_engine_state(is_enabled=False)
        return {"success": True, "message": "Engine disabled"}

# Import database AFTER class definition to avoid circular import
from .database import database

engine = Engine()
