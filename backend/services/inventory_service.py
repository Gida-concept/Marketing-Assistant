import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Local imports
from ..database import database
from ..models import TargetModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self):
        pass

    async def get_audited_count(self) -> int:
        """Get count of leads with status AUDITED"""
        try:
            return await database.count_leads_by_status("AUDITED")
        except Exception as e:
            logger.error(f"Error getting audited count: {str(e)}")
            return 0

    async def get_emailed_count(self) -> int:
        """Get count of leads with status EMAILED"""
        try:
            return await database.count_leads_by_status("EMAILED")
        except Exception as e:
            logger.error(f"Error getting emailed count: {str(e)}")
            return 0

    async def get_scraped_count(self) -> int:
        """Get count of leads with status SCRAPED"""
        try:
            return await database.count_leads_by_status("SCRAPED")
        except Exception as e:
            logger.error(f"Error getting scraped count: {str(e)}")
            return 0

    async def get_next_target(self,
                              industry_idx: int,
                              location_idx: int,
                              state_idx: int) -> Optional[TargetModel]:
        """
        Get the next target based on current indices
        Returns None if no targets exist
        """
        try:
            # Get all targets from database
            targets = await database.get_all_targets()

            if not targets:
                logger.info("No targets configured in the system")
                return None

            # Flatten targets into list for indexing
            # This creates a sequence: (industry1,country1), (industry1,country2), ...
            flat_targets = []
            for target in targets:
                flat_targets.append({
                    'target': target,
                    'type': 'country'
                })
                # If state is specified, also create state-specific targets
                if target.state:
                    flat_targets.append({
                        'target': target,
                        'type': 'state'
                    })

            if not flat_targets:
                return None

            # Calculate current position in flattened list
            current_position = (industry_idx * 2) + location_idx
            if state_idx > 0:
                current_position += 1  # Offset for state

            # Wrap around if we've gone past the end
            target_index = current_position % len(flat_targets)
            selected = flat_targets[target_index]

            logger.info(
                f"Selected target: {selected['target'].industry} in {selected['target'].country} ({selected['type']})")
            return selected['target']

        except Exception as e:
            logger.error(f"Error selecting next target: {str(e)}", exc_info=True)
            return None

    async def get_current_target(self,
                                 industry_idx: int,
                                 location_idx: int,
                                 state_idx: int) -> Optional[Dict[str, str]]:
        """
        Get current target information for reporting
        Returns dict with industry, country, state
        """
        try:
            target = await self.get_next_target(industry_idx, location_idx, state_idx)
            if not target:
                return None

            return {
                'industry': target.industry,
                'country': target.country,
                'state': target.state
            }
        except Exception as e:
            logger.error(f"Error getting current target: {str(e)}")
            return None


# Global inventory_service instance
inventory_service = InventoryService()