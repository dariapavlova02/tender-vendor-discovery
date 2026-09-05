"""Bounded, isolated downloads of tender attachments from API metadata."""
from __future__ import annotations

import logging
import math
import ssl
import time
import urllib.request
from http.client import HTTPException
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import certifi

from ..config import paths
from ..models import AttachmentMetadata

logger = logging.getLogger(__name__)


def _validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Attachment URL must be HTTP(S) without embedded credentials")


class _HTTPRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class DocumentFetcher:
    """Download attachments; failures are logged and available in ``failures``.

    Each file has isolated storage. Limits apply per attachment; ``timeout`` is
    the socket timeout and ``total_timeout`` is checked between bounded reads.
    """

    def __init__(self, download_dir: Path | None = None, *, timeout: float = 20,
                 max_bytes: int = 20 * 1024 * 1024, total_timeout: float = 120) -> None:
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool):
            raise ValueError("max_bytes must be an integer")
        if not all(math.isfinite(value) and value > 0 for value in (timeout, max_bytes, total_timeout)):
            raise ValueError("Download limits must be finite and positive")
        self.download_dir = Path(download_dir or (paths.data_dir / "attachments"))
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.timeout, self.max_bytes, self.total_timeout = timeout, max_bytes, total_timeout
        self.failures: list[dict[str, str]] = []
        context = ssl.create_default_context(cafile=certifi.where())
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context), _HTTPRedirects(),
        )

    def fetch(self, attachments: Iterable[AttachmentMetadata]) -> list[Path]:
        saved: list[Path] = []
        self.failures = []
        for attachment in attachments:
            target = None
            directory = None
            filename = "attachment"
            try:
                if not attachment.url:
                    raise ValueError("Attachment URL is missing")
                _validate_url(attachment.url)
                raw_name = attachment.filename or unquote(urlsplit(attachment.url).path).split("/")[-1]
                filename = Path(raw_name.replace("\\", "/")).name
                if filename in {"", ".", ".."}:
                    filename = "attachment"
                if any(ord(char) < 32 for char in filename) or len(filename.encode("utf-8")) > 240:
                    raise ValueError("Invalid attachment filename")
                directory = self.download_dir / uuid4().hex
                directory.mkdir(exist_ok=False)
                target = directory / filename
                deadline = time.monotonic() + self.total_timeout
                with self._opener.open(attachment.url, timeout=self.timeout) as response:
                    size = response.headers.get("Content-Length")
                    declared_size = int(size) if size is not None else None
                    if declared_size is not None and not 0 <= declared_size <= self.max_bytes:
                        raise ValueError("Invalid or oversized attachment length")
                    received = 0
                    with target.open("xb") as stream:
                        while True:
                            if time.monotonic() >= deadline:
                                raise TimeoutError("Attachment exceeded total download time")
                            block = response.read(min(64 * 1024, self.max_bytes - received + 1))
                            if not block:
                                break
                            received += len(block)
                            if received > self.max_bytes:
                                raise ValueError("Attachment exceeds size limit")
                            stream.write(block)
                    if declared_size is not None and received != declared_size:
                        raise ValueError("Incomplete attachment download")
                saved.append(target)
            except (OSError, ValueError, HTTPException) as exc:
                if target is not None:
                    target.unlink(missing_ok=True)
                if directory is not None:
                    directory.rmdir()
                # Exception messages/URLs can contain signed query strings or credentials.
                self.failures.append({"filename": filename, "error": type(exc).__name__})
                logger.warning("Attachment %r could not be downloaded (%s)", filename, type(exc).__name__)
        return saved
