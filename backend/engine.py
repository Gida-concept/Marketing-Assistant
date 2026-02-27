import httpx
import asyncio
import re
from .database import database

class Engine:
    def __init__(self):
        self.is_running = False
        self.serp_base_url = "https://serpapi.com/search"
        # Patterns to skip directory/listing sites
        self.skip_patterns = [
            r'builtin\.com', r'builtinsf\.com', r'thegoodtrade\.com',
            r'toddshelton\.com', r'directory', r'listings?', r'blog\.about',
            r'/blog/', r'/features/', r'/companies/.*type', r'fashion-companies'
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
        query = f'"{target.industry}" company website "{target.country}"'
        if target.state:
            query += f' "{target.state}"'
        
        params = {
            "engine": "google",
            "q": query,
            "api_key": settings.serp_api_key,
            "num": 10,
            "gl": "us",
            "filter": "0"  # Disable Google's "similar results" filter
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                serp_resp = await client.get(self.serp_base_url, params=params)
                serp_resp.raise_for_status()
                results = serp_resp.json().get("organic_results", [])
                
                scraped = 0
                for result in results[:10]:
                    url = result.get("link")
                    title = result.get("title", "")
                    
                    # Skip bad URLs BEFORE auditing
                    if not url or "google.com" in url or self._should_skip_url(url, title):
                        logger.info(f"Skipped (directory/listing): {url}")
                        continue
                    
                    try:
                        audit_resp = await client.post(
                            "http://localhost:3001/audit",
                            json={"url": url},
                            timeout=15
                        )
                        audit_resp.raise_for_status()
                        audit_data = audit_resp.json()
                        
                        if audit_data.get("success"):
                            data = audit_data["data"]
                            # Only save leads with emails OR good metrics
                            if data.get("emails") or (data.get("ssl") and data.get("h1_count", 0) > 0):
                                await database.save_lead({
                                    "business_name": title or "Unknown Business",
                                    "industry": target.industry,
                                    "country": target.country,
                                    "state": target.state,
                                    "website": url,
                                    "email": data["emails"][0] if data.get("emails") else None,
                                    "load_time": data.get("load_time"),
                                    "ssl_status": data.get("ssl"),
                                    "h1_count": data.get("h1_count"),
                                    "priority_score": self.calculate_priority(data),
                                    "status": "AUDITED" if data.get("emails") else "SCRAPED"
                                })
                                scraped += 1
                                logger.info(f"Saved lead: {title} | Email: {data.get('emails', [None])[0]}")
                                if scraped >= 5:
                                    break
                    
                    except Exception as e:
                        error_detail = str(e)
                        if "timeout" in error_detail.lower():
                            error_detail = "Timeout (site too slow)"
                        elif "connect" in error_detail.lower():
                            error_detail = "Connection failed"
                        logger.warning(f"Audit failed for {url}: {error_detail}")
                        continue
            
            return {"success": True, "message": f"Scraped {scraped} qualified leads"}
        
        except Exception as e:
            logger.error(f"SerpApi error: {e}")
            return {"success": False, "message": f"SerpApi failed: {str(e)}"}
    
    def _should_skip_url(self, url, title):
        """Skip directory/listing sites that won't have business emails"""
        url_lower = url.lower()
        title_lower = title.lower() if title else ""
        
        for pattern in self.skip_patterns:
            if re.search(pattern, url_lower) or re.search(pattern, title_lower):
                return True
        
        # Skip non-business TLDs
        if not re.search(r'\.(com|net|org|io|co)$', url_lower):
            return True
        
        # Skip URLs with these path patterns
        skip_paths = ['/careers', '/jobs', '/about', '/contact', '/team', '/press']
        for path in skip_paths:
            if path in url_lower:
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
        return {"success": True, "message": "Engine enabled. Will run immediately and daily at 8:00 AM UTC"}
    
    async def stop(self):
        await database.update_engine_state(is_enabled=False)
        return {"success": True, "message": "Engine disabled"}

engine = Engine()
