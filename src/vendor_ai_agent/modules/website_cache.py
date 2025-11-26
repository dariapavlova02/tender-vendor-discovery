"""Domain-level caching for website scraping results."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CachedWebsiteContent:
    """Cached content for a single domain."""
    domain: str
    scraped_at: str
    ttl_hours: int
    content: Dict[str, Any]
    contacts: Dict[str, List[str]]
    metadata: Dict[str, Any]


class WebsiteCache:
    """Manages domain-level caching for website scraping results."""
    
    def __init__(self, cache_dir: Path | str = "outputs/cache/websites", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.ttl_hours = ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Website cache initialized: {self.cache_dir} (TTL: {ttl_hours}h)")
    
    def _get_cache_path(self, domain: str) -> Path:
        """Generate cache file path for a domain."""
        domain_hash = hashlib.md5(domain.encode()).hexdigest()
        return self.cache_dir / f"{domain_hash}.json"
    
    def get(self, domain: str) -> Optional[CachedWebsiteContent]:
        """Retrieve cached content for a domain if valid."""
        cache_path = self._get_cache_path(domain)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            scraped_at = datetime.fromisoformat(data['scraped_at'])
            ttl = timedelta(hours=data.get('ttl_hours', self.ttl_hours))
            
            if datetime.now(timezone.utc) - scraped_at > ttl:
                logger.debug(f"Cache expired for {domain}")
                cache_path.unlink()
                return None
            
            logger.debug(f"Cache hit for {domain}")
            return CachedWebsiteContent(**data)
        
        except Exception as e:
            logger.warning(f"Failed to read cache for {domain}: {e}")
            return None
    
    def set(
        self,
        domain: str,
        content: Dict[str, Any],
        contacts: Dict[str, List[str]],
        metadata: Dict[str, Any]
    ) -> None:
        """Cache content for a domain."""
        cache_path = self._get_cache_path(domain)
        
        cached = CachedWebsiteContent(
            domain=domain,
            scraped_at=datetime.now(timezone.utc).isoformat(),
            ttl_hours=self.ttl_hours,
            content=content,
            contacts=contacts,
            metadata=metadata
        )
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(cached), f, indent=2)
            logger.debug(f"Cached content for {domain}")
        except Exception as e:
            logger.warning(f"Failed to write cache for {domain}: {e}")
    
    def clear_expired(self) -> int:
        """Remove all expired cache entries. Returns count of removed entries."""
        removed = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                scraped_at = datetime.fromisoformat(data['scraped_at'])
                ttl = timedelta(hours=data.get('ttl_hours', self.ttl_hours))
                
                if datetime.now(timezone.utc) - scraped_at > ttl:
                    cache_file.unlink()
                    removed += 1
            except Exception as e:
                logger.warning(f"Failed to check cache file {cache_file}: {e}")
        
        if removed:
            logger.info(f"Cleared {removed} expired cache entries")
        return removed
    
    def clear_all(self) -> int:
        """Remove all cache entries. Returns count of removed entries."""
        removed = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                removed += 1
            except Exception as e:
                logger.warning(f"Failed to remove cache file {cache_file}: {e}")
        
        if removed:
            logger.info(f"Cleared {removed} cache entries")
        return removed
