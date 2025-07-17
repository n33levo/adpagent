#!/usr/bin/env python3
"""
Resume downloader with parallel processing
"""

import asyncio
import aiohttp
import aiofiles
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import hashlib

from config import CONFIG, LOGGER
from models import CandidateModel, DownloadStatus
from browser import BrowserAutomation

class DownloadAttempt:
    def __init__(self, candidate_id: str, candidate_name: str, status: DownloadStatus, 
                 file_path: Optional[Path] = None, error_message: Optional[str] = None):
        self.candidate_id = candidate_id
        self.candidate_name = candidate_name
        self.status = status
        self.file_path = file_path
        self.error_message = error_message
        self.timestamp = datetime.now()

class ResumeDownloader:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def download_all_resumes(
        self, 
        candidates: List[CandidateModel], 
        browser: BrowserAutomation,
        config: Dict[str, Any]
    ) -> List[DownloadAttempt]:
        if not candidates:
            return []

        LOGGER.info(f"Starting download process for {len(candidates)} candidates")
        
        download_dir = Path(config['download']['folder'])
        download_dir.mkdir(parents=True, exist_ok=True)
        
        timeout = aiohttp.ClientTimeout(total=config['download']['timeout_seconds'])
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session
            
            semaphore = asyncio.Semaphore(config['download']['max_concurrent'])
            
            tasks = []
            for candidate in candidates:
                task = self._download_candidate_resume(
                    candidate, browser, download_dir, config, semaphore
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and convert to DownloadAttempt objects
            valid_results = []
            for result in results:
                if isinstance(result, DownloadAttempt):
                    valid_results.append(result)
                elif isinstance(result, Exception):
                    LOGGER.error(f"Download task failed: {str(result)}")
        
        successful = sum(1 for r in valid_results if r.status == DownloadStatus.SUCCESS)
        LOGGER.info(f"Download completed: {successful}/{len(valid_results)} successful")
        
        return valid_results

    async def _download_candidate_resume(
        self,
        candidate: CandidateModel,
        browser: BrowserAutomation,
        download_dir: Path,
        config: Dict[str, Any],
        semaphore: asyncio.Semaphore
    ) -> DownloadAttempt:
        async with semaphore:
            try:
                # Navigate to candidate profile
                await browser.page.goto(candidate.url)
                await browser.page.wait_for_load_state('networkidle')
                
                # Find resume download link
                download_url = await self._find_resume_download_url(browser, candidate)
                
                if not download_url:
                    return DownloadAttempt(
                        candidate.id, candidate.name, 
                        DownloadStatus.NOT_FOUND, 
                        error_message="Resume download URL not found"
                    )
                
                # Download the file
                file_path = await self._download_file(download_url, candidate, download_dir)
                
                if await self._validate_pdf_file(file_path):
                    candidate.mark_processed(DownloadStatus.SUCCESS, file_path)
                    LOGGER.info(f"✓ Downloaded resume for {candidate.name}")
                    return DownloadAttempt(candidate.id, candidate.name, DownloadStatus.SUCCESS, file_path)
                else:
                    return DownloadAttempt(
                        candidate.id, candidate.name, 
                        DownloadStatus.FAILED, 
                        error_message="File validation failed"
                    )
                    
            except Exception as e:
                error_message = str(e)
                candidate.mark_processed(DownloadStatus.FAILED, error=error_message)
                LOGGER.error(f"✗ Failed to download resume for {candidate.name}: {error_message}")
                return DownloadAttempt(
                    candidate.id, candidate.name, 
                    DownloadStatus.FAILED, 
                    error_message=error_message
                )

    async def _find_resume_download_url(self, browser: BrowserAutomation, candidate: CandidateModel) -> Optional[str]:
        try:
            download_selectors = [
                'a[href*="resume"]',
                'a[href*="cv"]',
                'a[href*=".pdf"]',
                'a[href*="download"]',
                '.resume-download',
                '.cv-download'
            ]
            
            for selector in download_selectors:
                try:
                    element = await browser.page.wait_for_selector(selector, timeout=2000)
                    if element:
                        href = await element.get_attribute('href')
                        if href and href.endswith('.pdf'):
                            if href.startswith('/'):
                                current_url = browser.page.url
                                base_url = f"{current_url.split('/')[0]}//{current_url.split('/')[2]}"
                                href = base_url + href
                            return href
                except:
                    continue
            
            return None
            
        except Exception as e:
            LOGGER.error(f"Error finding resume URL for {candidate.name}: {str(e)}")
            return None

    async def _download_file(self, download_url: str, candidate: CandidateModel, download_dir: Path) -> Path:
        safe_name = self._generate_safe_filename(candidate.name)
        file_path = download_dir / f"{safe_name}.pdf"
        
        counter = 1
        while file_path.exists():
            file_path = download_dir / f"{safe_name}_{counter}.pdf"
            counter += 1
        
        async with self.session.get(download_url) as response:
            if response.status == 200:
                content = await response.read()
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(content)
                return file_path
            else:
                raise Exception(f"HTTP {response.status}")

    async def _validate_pdf_file(self, file_path: Path) -> bool:
        try:
            if not file_path.exists():
                return False
            
            file_size = file_path.stat().st_size
            if file_size < 1024:  # Less than 1KB
                return False
            
            async with aiofiles.open(file_path, 'rb') as f:
                header = await f.read(8)
                return header.startswith(b'%PDF-')
                
        except:
            return False

    def _generate_safe_filename(self, candidate_name: str) -> str:
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        safe_name = ''.join(c for c in candidate_name if c in safe_chars)
        safe_name = safe_name.replace(' ', '_').strip('_.')[:50]
        
        if not safe_name:
            hash_obj = hashlib.md5(candidate_name.encode())
            safe_name = f"candidate_{hash_obj.hexdigest()[:8]}"
        
        return safe_name
