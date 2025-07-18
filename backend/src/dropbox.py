import re
import logging
import os
import zipfile
import json
from typing import List
from urllib.parse import urlparse, parse_qs, unquote
from .base import BaseDownloader

logger = logging.getLogger('file_downloader')

class DropboxDownloader(BaseDownloader):
    """Dropbox file downloader."""

    def __init__(self, download_path):
        super().__init__(download_path)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (File Downloader)'
        })

    def can_handle_url(self, url: str) -> bool:
        """Check if the URL is a Dropbox link."""
        patterns = [
            r'https://www\.dropbox\.com/s/[^/]+/[^/\s?]+', # Old file links
            r'https://www\.dropbox\.com/scl/.+',          # New file/folder links
            r'https://www\.dropbox\.com/sh/.+',           # Old folder links
        ]
        return any(re.match(pattern, url) for pattern in patterns)

    def download_file(self, url: str) -> List[str]:
        """Download file(s) from Dropbox URL. Handles folder links by scraping."""
        try:
            # Check if it's a folder link
            if '/scl/fo/' in url or '/sh/' in url:
                logger.info(f"Dropbox folder link detected. Scraping for individual files: {url}")
                return self._download_folder_contents(url)
            else:
                logger.info(f"Processing Dropbox file URL: {url}")
                return self._download_single_file(url)
        except Exception as e:
            logger.error(f"Error processing Dropbox URL {url}: {str(e)}")
            return []

    def _download_folder_contents(self, folder_url: str) -> List[str]:
        """Scrapes a Dropbox folder page and downloads each file."""
        # Ensure dl=0 to get the HTML page, not a zip download
        page_url = folder_url.replace('dl=1', 'dl=0')
        if 'dl=' not in page_url:
            if '?' in page_url:
                page_url += '&dl=0'
            else:
                page_url += '?dl=0'
        
        logger.info(f"Fetching folder page: {page_url}")
        response = self.session.get(page_url, follow_redirects=True)
        response.raise_for_status()
        html_content = response.text

        # Find the preloaded state JSON. This is brittle and may break if Dropbox changes their site.
        match = re.search(r'preloadedState: ({.+?}),\n', html_content)
        if not match:
            logger.error("Could not find preloaded state JSON in Dropbox folder page. Cannot scrape for files.")
            return []

        try:
            preloaded_state = json.loads(match.group(1))
            # This path is a guess based on observing Dropbox's structure. It might break.
            entries = preloaded_state.get('sharing', {}).get('entries', [])
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse preloaded state JSON: {e}")
            return []

        if not entries:
            logger.warning("No file entries found in Dropbox folder.")
            return [] # No files to download is a success, but no files were downloaded.

        # Extract rlkey from original folder URL to append to file URLs
        parsed_folder_url = urlparse(folder_url)
        query_params = parse_qs(parsed_folder_url.query)
        rlkey = query_params.get('rlkey', [None])[0]

        downloaded_files = []
        for entry in entries:
            if entry.get('type') == 'file' and 'scl_id' in entry and 'name' in entry:
                file_scl_id = entry['scl_id']
                file_name = entry['name']
                file_url = f"https://www.dropbox.com/scl/fi/{file_scl_id}/{file_name}"
                if rlkey:
                    file_url += f"?rlkey={rlkey}"
                
                logger.info(f"Found file in folder: {file_name}")
                newly_downloaded = self._download_single_file(file_url)
                if newly_downloaded:
                    downloaded_files.extend(newly_downloaded)
                else:
                    logger.error(f"Failed to download file: {file_name} from {file_url}")
        
        return downloaded_files

    def _download_single_file(self, url: str) -> List[str]:
        """
        Downloads a single file from a direct Dropbox file URL.
        Returns a list containing the filename on success, otherwise an empty list.
        """
        try:
            # Convert share URL to direct download URL
            download_url = url
            if 'dl=0' in download_url or 'dl=1' not in download_url:
                download_url = download_url.replace('?dl=0', '?dl=1')
                if '?' not in download_url:
                    download_url += '?dl=1'
                elif 'dl=' not in download_url:
                    download_url += '&dl=1'

            logger.info(f"Converted to download URL: {download_url}")

            with self.session.stream('GET', download_url, follow_redirects=True) as r:
                r.raise_for_status()

                filename = None
                content_disposition = r.headers.get('content-disposition')
                if content_disposition:
                    # Handles RFC 5987 encoded filenames.
                    filename_match = re.search(r"filename\*=UTF-8''([^']*)", content_disposition)
                    if not filename_match:
                        filename_match = re.search(r'filename="([^"]+)"', content_disposition)
                    
                    if filename_match:
                        filename = unquote(filename_match.group(1))

                if not filename:
                    # Fallback to URL parsing
                    filename = url.split('/')[-1].split('?')[0]
                
                output_path = f"{self.download_path}/{filename}"

                with open(output_path, 'wb') as f:
                    for chunk in r.iter_bytes(chunk_size=8192):
                        f.write(chunk)

            logger.info(f"Successfully downloaded Dropbox file: {filename}")
            return [filename]
        except Exception as e:
            logger.error(f"Error downloading single file from Dropbox {url}: {str(e)}")
            return []
