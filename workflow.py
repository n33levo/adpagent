#!/usr/bin/env python3
"""
LangGraph workflow for ADP Resume Downloader
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END

from config import CONFIG, LOGGER
from models import WorkflowGraphState, WorkflowState, LoginStatus, DownloadStatus
from browser import BrowserAutomation
from downloader import ResumeDownloader

class WorkflowOrchestrator:
    def __init__(self):
        self.browser = BrowserAutomation()
        self.downloader = ResumeDownloader()

    async def setup_browser_node(self, state: WorkflowGraphState) -> WorkflowGraphState:
        try:
            LOGGER.info("Setting up browser")
            state['current_state'] = WorkflowState.BROWSER_SETUP
            
            browser_state = await self.browser.setup_browser()
            state['browser_state'] = browser_state
            
            if browser_state.is_setup:
                LOGGER.info("Browser setup successful")
            else:
                state['current_state'] = WorkflowState.ERROR
                state['error_message'] = browser_state.error_message or "Browser setup failed"
                state['should_continue'] = False
                
        except Exception as e:
            LOGGER.error(f"Browser setup error: {str(e)}")
            state['current_state'] = WorkflowState.ERROR
            state['error_message'] = str(e)
            state['should_continue'] = False
            
        return state

    async def login_node(self, state: WorkflowGraphState) -> WorkflowGraphState:
        try:
            LOGGER.info("Attempting login")
            
            login_url = state['config']['adp']['login_url']
            browser_state = await self.browser.navigate_to_login(login_url)
            state['browser_state'] = browser_state
            
            if not browser_state.current_url:
                state['current_state'] = WorkflowState.LOGIN_FAILED
                state['error_message'] = "Failed to navigate to login page"
                return state
            
            username = state['config']['adp']['username']
            password = state['config']['adp']['password']
            
            login_status, browser_state = await self.browser.attempt_login(username, password)
            state['browser_state'] = browser_state
            
            if login_status == LoginStatus.SUCCESS:
                LOGGER.info("Login successful")
                state['current_state'] = WorkflowState.LOGIN_SUCCESS
            else:
                LOGGER.error(f"Login failed: {login_status.value}")
                state['current_state'] = WorkflowState.LOGIN_FAILED
                state['error_message'] = f"Login failed: {login_status.value}"
                
        except Exception as e:
            LOGGER.error(f"Login error: {str(e)}")
            state['current_state'] = WorkflowState.LOGIN_FAILED
            state['error_message'] = str(e)
            
        return state

    async def navigate_to_candidates_node(self, state: WorkflowGraphState) -> WorkflowGraphState:
        try:
            LOGGER.info("Navigating to candidates page")
            
            success, _ = await self.browser.navigate_to_candidates()
            
            if success:
                LOGGER.info("Navigation successful")
                state['current_state'] = WorkflowState.NAVIGATION_SUCCESS
            else:
                LOGGER.error("Navigation failed")
                state['current_state'] = WorkflowState.NAVIGATION_FAILED
                state['error_message'] = "Failed to navigate to candidates page"
                
        except Exception as e:
            LOGGER.error(f"Navigation error: {str(e)}")
            state['current_state'] = WorkflowState.NAVIGATION_FAILED
            state['error_message'] = str(e)
            
        return state

    async def extract_candidates_node(self, state: WorkflowGraphState) -> WorkflowGraphState:
        try:
            LOGGER.info("Extracting candidates")
            
            max_pages = state['config']['extraction']['max_pages']
            current_page = 1
            
            while current_page <= max_pages:
                page_candidates = await self.browser.extract_candidates_from_page()
                
                if page_candidates:
                    state['candidates'].extend(page_candidates)
                    state['stats'].total_candidates += len(page_candidates)
                    LOGGER.info(f"Found {len(page_candidates)} candidates on page {current_page}")
                
                # Try to go to next page
                if current_page < max_pages:
                    has_next = await self.browser.navigate_to_next_page()
                    if not has_next:
                        break
                
                current_page += 1
            
            LOGGER.info(f"Extraction complete. Total candidates: {len(state['candidates'])}")
            state['current_state'] = WorkflowState.EXTRACTION_COMPLETE
            
        except Exception as e:
            LOGGER.error(f"Extraction error: {str(e)}")
            state['current_state'] = WorkflowState.ERROR
            state['error_message'] = str(e)
            
        return state

    async def download_resumes_node(self, state: WorkflowGraphState) -> WorkflowGraphState:
        try:
            LOGGER.info("Starting resume downloads")
            
            if not state['candidates']:
                LOGGER.warning("No candidates to download")
                state['current_state'] = WorkflowState.DOWNLOAD_COMPLETE
                return state
            
            download_results = await self.downloader.download_all_resumes(
                candidates=state['candidates'],
                browser=self.browser,
                config=state['config']
            )
            
            # Update statistics
            for result in download_results:
                if result.status == DownloadStatus.SUCCESS:
                    state['stats'].successful_downloads += 1
                else:
                    state['stats'].failed_downloads += 1
            
            LOGGER.info(f"Downloads complete: {state['stats'].successful_downloads} successful, "
                       f"{state['stats'].failed_downloads} failed")
            
            state['current_state'] = WorkflowState.DOWNLOAD_COMPLETE
            
        except Exception as e:
            LOGGER.error(f"Download error: {str(e)}")
            state['current_state'] = WorkflowState.ERROR
            state['error_message'] = str(e)
            
        return state

    async def cleanup_node(self, state: WorkflowGraphState) -> WorkflowGraphState:
        try:
            LOGGER.info("Cleaning up")
            await self.browser.cleanup()
            
            if state['stats'].successful_downloads > 0:
                state['current_state'] = WorkflowState.COMPLETED
            else:
                state['current_state'] = WorkflowState.ERROR
                if not state.get('error_message'):
                    state['error_message'] = "No resumes downloaded"
            
            state['should_continue'] = False
            
        except Exception as e:
            LOGGER.error(f"Cleanup error: {str(e)}")
            state['current_state'] = WorkflowState.ERROR
            state['error_message'] = str(e)
            state['should_continue'] = False
            
        return state

    def should_continue_after_login(self, state: WorkflowGraphState) -> str:
        return "navigate_to_candidates" if state['current_state'] == WorkflowState.LOGIN_SUCCESS else "cleanup"

    def should_continue_after_navigation(self, state: WorkflowGraphState) -> str:
        return "extract_candidates" if state['current_state'] == WorkflowState.NAVIGATION_SUCCESS else "cleanup"

    def should_continue_after_extraction(self, state: WorkflowGraphState) -> str:
        return "download_resumes" if state['current_state'] == WorkflowState.EXTRACTION_COMPLETE else "cleanup"

def create_workflow_graph() -> StateGraph:
    LOGGER.info("Creating LangGraph workflow")
    
    orchestrator = WorkflowOrchestrator()
    workflow = StateGraph(WorkflowGraphState)
    
    # Add nodes
    workflow.add_node("setup_browser", orchestrator.setup_browser_node)
    workflow.add_node("login", orchestrator.login_node)
    workflow.add_node("navigate_to_candidates", orchestrator.navigate_to_candidates_node)
    workflow.add_node("extract_candidates", orchestrator.extract_candidates_node)
    workflow.add_node("download_resumes", orchestrator.download_resumes_node)
    workflow.add_node("cleanup", orchestrator.cleanup_node)
    
    # Set entry point
    workflow.set_entry_point("setup_browser")
    
    # Add edges
    workflow.add_edge("setup_browser", "login")
    
    workflow.add_conditional_edges(
        "login",
        orchestrator.should_continue_after_login,
        {"navigate_to_candidates": "navigate_to_candidates", "cleanup": "cleanup"}
    )
    
    workflow.add_conditional_edges(
        "navigate_to_candidates",
        orchestrator.should_continue_after_navigation,
        {"extract_candidates": "extract_candidates", "cleanup": "cleanup"}
    )
    
    workflow.add_conditional_edges(
        "extract_candidates",
        orchestrator.should_continue_after_extraction,
        {"download_resumes": "download_resumes", "cleanup": "cleanup"}
    )
    
    workflow.add_edge("download_resumes", "cleanup")
    workflow.add_edge("cleanup", END)
    
    return workflow.compile()
