import httpx
import asyncio
from datetime import datetime, timedelta
from .database import database, Leads, Targets

class Engine:
    def __init__(self):
        self.is_running = False
        self.serp_base_url = "https://serpapi.com/search"
    
    async def run(self):
        """Main engine execution cycle"""
        if self.is_running:
            return {"success": False, "message": "Engine already running"}
        
        self.is_running = True
        try:
            # 1. Get system settings
            settings = await database.get_settings()
            config = await database.get_config()
            stats = await database.get_stats()
            
            # 2. Check email quota
            if stats.emails_sent_today >= settings.daily_email_limit:
                return {"success": False, "message": f"Daily email limit ({settings.daily_email_limit}) reached"}
            
            # 3. Get current target
            targets = await database.get_all_targets()
            if not targets:
                return {"success": False, "message": "No targets configured"}
            
            target = targets[config.industry_idx % len(targets)]
            
            # 4. Get audited lead count
            audited_count = await database.count_leads_by_status("AUDITED")
            
            # 5. Scrape if inventory low
            if audited_count < settings.inventory_threshold:
                await self.scrape_leads(target, settings)
            
            # 6. Email leads if available
            await self.email_leads(settings, stats)
            
            # 7. Update config rotation
            await database.update_config(
                industry_idx=(config.industry_idx + 1) % len(targets),
                location_idx=config.location_idx
            )
            
            return {"success": True, "message": "Engine cycle completed"}
        
        finally:
            self.is_running = False
    
    async def scrape_leads(self, target, settings):
        """Scrape leads using SerpApi + Puppeteer API"""
        try:
            # Build search query
            query = f"{target.industry} companies {target.country}"
            if target.state:
                query += f" {target.state}"
            
            # Call SerpApi
            params = {
                "engine": "google",
                "q": query,
                "api_key": settings.serp_api_key,
                "num": 10,
                "gl": "us"
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                serp_resp = await client.get(self.serp_base_url, params=params)
                serp_resp.raise_for_status()
                results = serp_resp.json().get("organic_results", [])
                
                # Audit each result via Puppeteer API
                for result in results[:5]:  # Limit to 5 for safety
                    url = result.get("link")
                    if not url or "google.com" in url:
                        continue
                    
                    # Call Puppeteer API for auditing (HEADLESS)
                    audit_resp = await client.post(
                        "http://localhost:3001/audit",
                        json={"url": url},
                        timeout=30
                    )
                    audit_data = audit_resp.json()
                    
                    if audit_data.get("success"):
                        data = audit_data["data"]
                        # Save lead
                        await database.save_lead({
                            "business_name": result.get("title", "Unknown"),
                            "industry": target.industry,
                            "country": target.country,
                            "state": target.state,
                            "website": url,
                            "email": data["emails"][0] if data.get("emails") else None,
                            "load_time": data.get("load_time"),
                            "ssl_status": data.get("ssl"),
                            "h1_count": data.get("h1_count"),
                            "priority_score": self.calculate_priority(data),
                            "status": "AUDITED"
                        })
        
        except Exception as e:
            print(f"Scraping error: {str(e)}")
            raise
    
    def calculate_priority(self, audit_data):
        """Calculate lead priority score (0-100)"""
        score = 50
        if audit_data.get("ssl"):
            score += 20
        if audit_data.get("load_time", 999) < 3.0:
            score += 20
        if audit_data.get("h1_count", 0) > 0:
            score += 10
        return min(100, max(0, score))
    
    async def email_leads(self, settings, stats):
        """Send outreach emails to audited leads"""
        # Placeholder - implement SMTP sending logic here
        pass
    
    async def start(self):
        await database.update_engine_state(is_enabled=True)
        return {"success": True, "message": "Engine enabled"}
    
    async def stop(self):
        await database.update_engine_state(is_enabled=False)
        return {"success": True, "message": "Engine disabled"}

engine = Engine()
