"""Shared HTTP client factory for connection pooling."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class HttpClientFactory:
    """Singleton factory for shared HTTP client with connection pooling."""
    
    _instance: Optional[httpx.AsyncClient] = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """Get or create the shared AsyncClient instance."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    logger.debug("Initializing shared HTTP client with connection pooling")
                    cls._instance = httpx.AsyncClient(
                        timeout=30.0,
                        follow_redirects=True,
                        http2=True,  # Enable HTTP/2
                        verify=False,  # Skip SSL verification for scraping (optional)
                        limits=httpx.Limits(
                            max_connections=100,      # Max total connections
                            max_keepalive_connections=50,  # Max idle connections to keep
                            keepalive_expiry=300,     # Keep connections alive for 5 mins
                        )
                    )
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        """Close the shared client if it exists."""
        if cls._instance:
            async with cls._lock:
                if cls._instance:
                    logger.debug("Closing shared HTTP client")
                    await cls._instance.aclose()
                    cls._instance = None
