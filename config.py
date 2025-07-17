#!/usr/bin/env python3
"""
Configuration management for ADP Resume Downloader
"""

import os
import logging
from typing import Optional
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ADPConfig(BaseModel):
    username: str
    password: str
    login_url: str

class DownloadConfig(BaseModel):
    folder: str = "./downloads"
    max_concurrent: int = 3
    timeout_seconds: int = 120
    max_retries: int = 3

class BrowserConfig(BaseModel):
    headless: bool = False
    timeout_seconds: int = 30

class ExtractionConfig(BaseModel):
    max_pages: int = 50
    delay_seconds: int = 2

class Config(BaseModel):
    adp: ADPConfig
    download: DownloadConfig
    browser: BrowserConfig
    extraction: ExtractionConfig
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

# Initialize configuration
CONFIG = Config(
    adp=ADPConfig(
        username=os.getenv("ADP_USERNAME", ""),
        password=os.getenv("ADP_PASSWORD", ""),
        login_url=os.getenv("ADP_LOGIN_URL", "")
    ),
    download=DownloadConfig(
        folder=os.getenv("DOWNLOAD_FOLDER", "./downloads"),
        max_concurrent=int(os.getenv("DOWNLOAD_MAX_CONCURRENT", "3")),
        timeout_seconds=int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "120")),
        max_retries=int(os.getenv("DOWNLOAD_MAX_RETRIES", "3"))
    ),
    browser=BrowserConfig(
        headless=os.getenv("BROWSER_HEADLESS", "false").lower() == "true",
        timeout_seconds=int(os.getenv("BROWSER_TIMEOUT_SECONDS", "30"))
    ),
    extraction=ExtractionConfig(
        max_pages=int(os.getenv("EXTRACTION_MAX_PAGES", "50")),
        delay_seconds=int(os.getenv("EXTRACTION_DELAY_SECONDS", "2"))
    ),
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('resume_downloader.log'),
        logging.StreamHandler()
    ]
)

LOGGER = logging.getLogger(__name__)
