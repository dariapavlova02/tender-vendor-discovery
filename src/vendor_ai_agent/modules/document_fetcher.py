"""Download tender attachments from API metadata."""
from __future__ import annotations

import ssl
import urllib.request
from pathlib import Path
from typing import Iterable, List

import certifi

from ..config import paths
from ..models import AttachmentMetadata


class DocumentFetcher:
    """Downloads attachment URLs to a local working directory."""

    def __init__(self, download_dir: Path | None = None) -> None:
        self.download_dir = download_dir or (paths.data_dir / "attachments")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    def fetch(self, attachments: Iterable[AttachmentMetadata]) -> List[Path]:
        saved: List[Path] = []
        for attachment in attachments:
            url = attachment.url
            if not url:
                continue
            filename = attachment.filename or url.split("/")[-1] or "attachment"
            target = self.download_dir / filename
            try:
                with urllib.request.urlopen(url, context=self._ssl_context) as response:
                    target.write_bytes(response.read())
                saved.append(target)
            except Exception:
                continue
        return saved
