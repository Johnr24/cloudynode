import re
import logging
import gdown
import os
from typing import List
from urllib.parse import parse_qs, urlparse
from .base import BaseDownloader

logger = logging.getLogger('file_downloader')

class GoogleDriveDownloader(BaseDownloader):
    """Google Drive file downloader."""

    def __init__(self, download_path):
        super().__init__(download_path)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (File Downloader)'
        })

    def can_handle_url(self, url: str) -> bool:
        """Check if the URL is a Google Drive link."""
        patterns = [
            r'https://drive\.google\.com/file/d/[^/\s?]+(?:/[^/\s?]*)?',
            r'https://drive\.google\.com/open\?id=[^/\s&]+',
            r'https://drive\.google\.com/uc\?id=[^/\s&]+'
        ]
        return any(re.match(pattern, url) for pattern in patterns)

    def download_file(self, url: str) -> List[str]:
        """Download file from Google Drive URL using gdown."""
        try:
            # Extract file ID from URL
            file_id = self._extract_file_id(url)
            if not file_id:
                logger.error("Could not extract file ID from Google Drive URL")
                return []

            logger.info(f"Processing Google Drive URL with file ID: {file_id}")

            # Use gdown to download the file. It returns the path on success.
            output_path = gdown.download(
                url=f"https://drive.google.com/uc?id={file_id}",
                output=str(self.download_path),
                quiet=False,
                fuzzy=True
            )

            if output_path:
                filename = os.path.basename(output_path)
                logger.info(f"Successfully downloaded Google Drive file: {filename}")
                return [filename]
            else:
                logger.error("Failed to download file from Google Drive")
                return []

        except Exception as e:
            logger.error(f"Error downloading from Google Drive: {str(e)}")
            return []

    def _extract_file_id(self, url: str) -> str:
        """Extract file ID from Google Drive URL."""
        if '/file/d/' in url:
            file_id = url.split('/file/d/')[1].split('/')[0]
            return file_id
        elif 'id=' in url:
            parsed = urlparse(url)
            file_id = parse_qs(parsed.query)['id'][0]
            return file_id
        return ''
