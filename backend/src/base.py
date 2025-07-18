import abc
import httpx
from typing import List


class BaseDownloader(abc.ABC):
    """Abstract base class for downloaders."""

    def __init__(self, download_path):
        self.download_path = download_path
        self.session = httpx.Client()

    @abc.abstractmethod
    def can_handle_url(self, url: str) -> bool:
        """Check if the downloader can handle the given URL."""
        raise NotImplementedError

    @abc.abstractmethod
    def download_file(self, url: str) -> List[str]:
        """
        Download file(s) from the URL.
        Returns a list of downloaded filenames, or an empty list on failure.
        """
        raise NotImplementedError
