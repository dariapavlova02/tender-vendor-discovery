import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from .models import APICache


class CacheManager:
    
    def __init__(self, session: Session, source: str):
        self.session = session
        self.source = source
    
    def _generate_cache_key(self, key_data: dict) -> str:
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(self, key_data: dict) -> Optional[dict]:
        cache_key = self._generate_cache_key(key_data)
        
        cache_entry = (
            self.session.query(APICache)
            .filter(
                APICache.source == self.source,
                APICache.cache_key == cache_key,
                APICache.expires_at > datetime.utcnow()
            )
            .first()
        )
        
        if cache_entry:
            cache_entry.hit_count += 1
            cache_entry.last_accessed_at = datetime.utcnow()
            self.session.commit()
            return cache_entry.response_data
        
        return None
    
    def set(
        self,
        key_data: dict,
        response_data: dict,
        ttl_days: int = 90
    ) -> None:
        cache_key = self._generate_cache_key(key_data)
        expires_at = datetime.utcnow() + timedelta(days=ttl_days)
        
        existing = (
            self.session.query(APICache)
            .filter(
                APICache.source == self.source,
                APICache.cache_key == cache_key
            )
            .first()
        )
        
        if existing:
            existing.response_data = response_data
            existing.expires_at = expires_at
            existing.last_accessed_at = datetime.utcnow()
        else:
            cache_entry = APICache(
                source=self.source,
                cache_key=cache_key,
                response_data=response_data,
                expires_at=expires_at
            )
            self.session.add(cache_entry)
        
        self.session.commit()
    
    def delete(self, key_data: dict) -> None:
        cache_key = self._generate_cache_key(key_data)
        
        self.session.query(APICache).filter(
            APICache.source == self.source,
            APICache.cache_key == cache_key
        ).delete()
        
        self.session.commit()
    
    def clear_expired(self) -> int:
        deleted = (
            self.session.query(APICache)
            .filter(
                APICache.source == self.source,
                APICache.expires_at <= datetime.utcnow()
            )
            .delete()
        )
        self.session.commit()
        return deleted
    
    def clear_all(self) -> int:
        deleted = (
            self.session.query(APICache)
            .filter(APICache.source == self.source)
            .delete()
        )
        self.session.commit()
        return deleted
    
    @classmethod
    def clear_all_sources(cls, session: Session) -> int:
        deleted = session.query(APICache).delete()
        session.commit()
        return deleted
