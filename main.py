#!/usr/bin/env python3
"""
ADP Resume Downloader - Main Application
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from config import CONFIG, LOGGER
from workflow import create_workflow_graph
from models import create_initial_state

async def main():
    try:
        LOGGER.info("=" * 50)
        LOGGER.info("ADP Resume Downloader Starting")
        LOGGER.info("=" * 50)
        
        # Create initial state
        initial_state = create_initial_state(CONFIG.dict())
        initial_state['stats'].start_workflow()
        
        # Create and execute workflow
        workflow_graph = create_workflow_graph()
        final_state = await workflow_graph.ainvoke(initial_state)
        
        # End workflow timing
        final_state['stats'].end_workflow()
        
        # Log results
        stats = final_state['stats']
        LOGGER.info("=" * 50)
        LOGGER.info("WORKFLOW COMPLETED")
        LOGGER.info("=" * 50)
        LOGGER.info(f"Total candidates: {stats.total_candidates}")
        LOGGER.info(f"Successful downloads: {stats.successful_downloads}")
        LOGGER.info(f"Failed downloads: {stats.failed_downloads}")
        LOGGER.info(f"Success rate: {stats.success_rate:.1f}%")
        LOGGER.info(f"Final state: {final_state['current_state'].value}")
        
        if final_state.get('error_message'):
            LOGGER.error(f"Final error: {final_state['error_message']}")
        
        LOGGER.info("=" * 50)
        
    except KeyboardInterrupt:
        LOGGER.info("Workflow interrupted by user")
        sys.exit(0)
    except Exception as e:
        LOGGER.error(f"Workflow failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())
