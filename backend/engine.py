import httpx
import asyncio
from datetime import datetime
from .database import database

class Engine:
    def __init__(self):
        self.is_running = False
        self.serp_base_url = "https://serpapi.com/search"
    
    async def run(self):
        if self.is_running:
            return {"success": False, "message": "Engine already running"}
        
        self.is_running = True
        try:
            settings = await database.get_settings()
            config = await database.get_config()
            stats = await database.get_stats()
            
            if stats.emails_sent_today >= settings.daily_email_limit:
                return {"success": False, "message": f"Daily email limit ({settings.daily_email_limit}) reached"}
            
            targets = await database.get_all_targets()
            if not targets:
                return {"success": False, "message": "No targets configured. Please add targets in the Targets section."}
            
            target = await database.get_target_by_indices(
                config.industry_idx, config.location_idx
            )
            
            audited_count = await database.count_leads_by_status("AUDITED")
            
            if audited_count < settings.inventory_threshold:
                await self.scrape_leads(target, settings)
            
            await database.update_config(
                industry_idx=(config.industry_idx + 1) % len(targets),
                location_idx=config.location_idx
            )
            
            return {"success": True, "message": "Engine cycle completed successfully"}
        
        except Exception as e:
            return {"success": False, "message": f"Engine error: {str(e)}"}
        finally:
            self.is_running = False
    
    async def scrape_leads(self, target, settings):
        query = f"{target.industry} companies {target.country}"
        if target.state:
            query += f" {target.state}"
        
        params = {
            "engine": "google",
            "q": query,
            "api_key": settings.serp_api_key,
            "num": 10,
            "gl": "us"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                serp_resp = await client.get(self.serp_base_url, params=params)
                serp_resp.raise_for_status()
                results = serp_resp.json().get("organic_results", [])
                
                for result in results[:5]:
                    url = result.get("link")
                    if not url or "google.com" in url:
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
                        print(f"Audit failed for {url}: {str(e)}")
                        continue
            
            except Exception as e:
                raise Exception(f"SerpApi request failed: {str(e)}")
    
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

engine = Engine()
