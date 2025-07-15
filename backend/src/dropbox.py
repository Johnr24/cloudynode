import re
import logging
from urllib.parse import urlparse, parse_qs
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
            r'https://www\.dropbox\.com/s/[^/]+/[^/\s?]+',
            r'https://www\.dropbox\.com/scl/[^/\s?]+/[^/\s?]+',
            r'https://www\.dropbox\.com/[^/\s?]+\?rlkey=[^/\s&]+'
        ]
        return any(re.match(pattern, url) for pattern in patterns)

    def download_file(self, url: str) -> bool:
        """Download file from Dropbox URL."""
        try:
            logger.info(f"Processing Dropbox URL: {url}")

            # Parse URL and parameters
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)

            # Convert share URL to direct download URL
            download_url = url

            # Handle rlkey parameter
            if 'rlkey' in query_params:
                rlkey = query_params['rlkey'][0]
                logger.info(f"Found rlkey parameter: {rlkey}")
                # Ensure rlkey is included in download URL
                if '?' not in download_url:
                    download_url += f'?rlkey={rlkey}'
                elif 'rlkey=' not in download_url:
                    download_url += f'&rlkey={rlkey}'

            # Add or update dl parameter for direct download
            if 'dl=0' in download_url or 'dl=1' not in download_url:
                download_url = download_url.replace('?dl=0', '?dl=1')
                if '?' not in download_url:
                    download_url += '?dl=1'
                elif 'dl=' not in download_url:
                    download_url += '&dl=1'

            logger.info(f"Converted to download URL: {download_url}")

            # Extract filename from URL
            filename = url.split('/')[-1].split('?')[0]

            return self._download_file_with_progress(download_url, filename)

        except Exception as e:
            logger.error(f"Error downloading from Dropbox: {str(e)}")
            return False