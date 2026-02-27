import httpx
import asyncio
import re
from .database import database

class Engine:
    def __init__(self):
        self.is_running = False
        self.serp_base_url = "https://serpapi.com/search"
        # Skip patterns for non-business URLs
        self.skip_patterns = [
            r'builtin\.com', r'builtinsf\.com', r'thegoodtrade\.com',
            r'toddshelton\.com', r'directory', r'listings?', r'blog',
            r'/blog/', r'/features/', r'/companies/', r'fashion-companies',
            r'wikipedia', r'linkedin\.com/company', r'crunchbase', r'glassdoor'
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
            print(f"Engine crash: {e}\n{traceback.format_exc()}")
            return {"success": False, "message": f"Engine error: {str(e)}"}
        finally:
            self.is_running = False
    
    async def scrape_leads(self, target, settings):
        # ✅ CORRECT: Use Google Maps engine for business listings
        query = f"{target.industry} companies"
        location = f"{target.state}, {target.country}" if target.state else target.country
        
        params = {
            "engine": "google_maps",  # ← CRITICAL FIX: Use Google Maps engine
            "q": query,
            "api_key": settings.serp_api_key,
            "type": "search",
            "ll": "@37.7749,-122.4194,14z",  # Default to SF if no coords
            "google_domain": "google.com",
            "hl": "en",
            "gl": "us"
        }
        
        # Add location-specific parameters
        if "united states" in target.country.lower() or "usa" in target.country.lower():
            if target.state:
                params["q"] = f"{target.industry} companies in {target.state}"
            else:
                params["q"] = f"{target.industry} companies in {target.country}"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                serp_resp = await client.get(self.serp_base_url, params=params)
                serp_resp.raise_for_status()
                data = serp_resp.json()
                
                # ✅ Google Maps returns "local_results" not "organic_results"
                results = data.get("local_results", [])
                if not results:
                    # Fallback to places search
                    params["type"] = "search"
                    serp_resp = await client.get(self.serp_base_url, params=params)
                    data = serp_resp.json()
                    results = data.get("local_results", [])
                
                scraped = 0
                for result in results[:10]:
                    business_name = result.get("title", "").strip()
                    website = result.get("website", "").strip()
                    address = result.get("address", "")
                    phone = result.get("phone", "")
                    
                    # Skip if no website or business name
                    if not website or not business_name or "No website" in website:
                        continue
                    
                    # Skip bad URLs BEFORE auditing
                    if self._should_skip_url(website, business_name):
                        print(f"Skipped (non-business): {business_name} | {website}")
                        continue
                    
                    try:
                        # ✅ Audit the BUSINESS website (not directory)
                        audit_resp = await client.post(
                            "http://localhost:3001/audit",
                            json={"url": website},
                            timeout=15
                        )
                        audit_resp.raise_for_status()
                        audit_data = audit_resp.json()
                        
                        if audit_data.get("success"):
                            ad = audit_data["data"]
                            # Save lead with business details
                            await database.save_lead({
                                "business_name": business_name,
                                "industry": target.industry,
                                "country": target.country,
                                "state": target.state,
                                "website": website,
                                "email": ad["emails"][0] if ad.get("emails") else None,
                                "load_time": ad.get("load_time"),
                                "ssl_status": ad.get("ssl"),
                                "h1_count": ad.get("h1_count"),
                                "priority_score": self.calculate_priority(ad),
                                "status": "AUDITED" if ad.get("emails") else "SCRAPED"
                            })
                            scraped += 1
                            print(f"✅ Saved: {business_name} | Email: {ad.get('emails', [None])[0]} | {website}")
                            if scraped >= 5:
                                break
                    
                    except Exception as e:
                        error_detail = str(e)
                        if "timeout" in error_detail.lower():
                            error_detail = "Timeout"
                        print(f"⚠️ Audit failed for {business_name} ({website}): {error_detail}")
                        continue
            
            return {"success": True, "message": f"Scraped {scraped} qualified business leads from Google Maps"}
        
        except Exception as e:
            print(f"❌ SerpApi error: {e}")
            return {"success": False, "message": f"SerpApi failed: {str(e)}"}
    
    def _should_skip_url(self, url, title):
        """Skip non-business URLs"""
        url_lower = url.lower()
        title_lower = title.lower() if title else ""
        
        # Skip social media/profile sites
        social_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com', 'pinterest.com']
        for domain in social_domains:
            if domain in url_lower:
                return True
        
        # Skip directories/aggregators
        for pattern in self.skip_patterns:
            if re.search(pattern, url_lower) or re.search(pattern, title_lower):
                return True
        
        # Skip non-commercial TLDs
        non_business_tlds = ['.edu', '.gov', '.org/wiki', 'wikipedia.org']
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
        return {"success": True, "message": "Engine enabled. Will run immediately and daily at 8:00 AM UTC"}
    
    async def stop(self):
        await database.update_engine_state(is_enabled=False)
        return {"success": True, "message": "Engine disabled"}

engine = Engine()
