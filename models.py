#!/usr/bin/env python3
"""
Data models for ADP Resume Downloader
"""

from typing import List, Dict, Optional, Any, TypedDict
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from pathlib import Path

class WorkflowState(Enum):
    INITIALIZED = "initialized"
    BROWSER_SETUP = "browser_setup"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    NAVIGATION_SUCCESS = "navigation_success"
    NAVIGATION_FAILED = "navigation_failed"
    EXTRACTION_COMPLETE = "extraction_complete"
    DOWNLOAD_COMPLETE = "download_complete"
    CLEANUP_COMPLETE = "cleanup_complete"
    ERROR = "error"
    COMPLETED = "completed"

class LoginStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"

class DownloadStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"

class CandidateModel(BaseModel):

    id: str
    name: str
    url: str
    req_job_title: Optional[str] = None  # New: Req# - Job Title for folder naming
    processed: bool = False
    download_status: Optional[DownloadStatus] = None
    download_path: Optional[Path] = None
    retry_count: int = 0
    error_message: Optional[str] = None

    def mark_processed(self, status: DownloadStatus, path: Optional[Path] = None, error: Optional[str] = None):
        self.processed = True
        self.download_status = status
        self.download_path = path
        self.error_message = error

class WorkflowStats(BaseModel):
    total_candidates: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def start_workflow(self):
        self.start_time = datetime.now()

    def end_workflow(self):
        self.end_time = datetime.now()

    @property
    def success_rate(self) -> float:
        if self.total_candidates == 0:
            return 0.0
        return (self.successful_downloads / self.total_candidates) * 100

class BrowserState(BaseModel):
    is_setup: bool = False
    current_url: Optional[str] = None
    is_logged_in: bool = False
    login_status: Optional[LoginStatus] = None
    error_message: Optional[str] = None

class WorkflowGraphState(TypedDict):
    current_state: WorkflowState
    error_message: Optional[str]
    should_continue: bool
    browser_state: BrowserState
    candidates: List[CandidateModel]
    stats: WorkflowStats
    config: Dict[str, Any]

def create_initial_state(config: Dict[str, Any]) -> WorkflowGraphState:
    return WorkflowGraphState(
        current_state=WorkflowState.INITIALIZED,
        error_message=None,
        should_continue=True,
        browser_state=BrowserState(),
        candidates=[],
        stats=WorkflowStats(),
        config=config
    )
