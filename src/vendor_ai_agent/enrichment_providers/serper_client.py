from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

import httpx
import requests


@dataclass
class SerperContact:
    emails: List[str]
    phones: List[str]
    website: Optional[str] = None
    confidence: float = 0.0


@dataclass
class SerperResult:
    website: Optional[str] = None
    contacts: Optional[SerperContact] = None
    raw_response: Optional[dict] = None


class SerperClient:
    def __init__(self, api_key: str, timeout: int = 10):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://google.serper.dev/search"
        self.places_url = "https://google.serper.dev/places"
        self.logger = logging.getLogger(__name__)
        
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        self.phone_pattern = re.compile(
            r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
        )
    
    def search_company(
        self,
        company_name: str,
        include_contacts: bool = True,
        query: Optional[str] = None,
    ) -> SerperResult:
        if query is None:
            if include_contacts:
                query = f"{company_name} official website contact email phone"
            else:
                query = f"{company_name} official website"
        
        self.logger.debug(f"Serper query: {query}")
        
        try:
            response = requests.post(
                self.base_url,
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json={"q": query, "num": 5},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            website = self._extract_website(data, company_name)
            contacts = self._extract_contacts(data) if include_contacts else None
            
            return SerperResult(
                website=website,
                contacts=contacts,
                raw_response=data
            )
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Serper API error: {e}")
            return SerperResult()
    
    async def search_company_async(
        self,
        company_name: str,
        include_contacts: bool = True,
        query: Optional[str] = None,
    ) -> SerperResult:
        if query is None:
            if include_contacts:
                query = f"{company_name} official website contact email phone"
            else:
                query = f"{company_name} official website"
        
        self.logger.debug(f"Serper query (async): {query}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "X-API-KEY": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={"q": query, "num": 5}
                )
                response.raise_for_status()
                data = response.json()
                
                website = self._extract_website(data, company_name)
                contacts = self._extract_contacts(data) if include_contacts else None
                
                return SerperResult(
                    website=website,
                    contacts=contacts,
                    raw_response=data
                )
                
        except (httpx.HTTPError, Exception) as e:
            self.logger.error(f"Serper API error (async): {e}")
            return SerperResult()
    
    def _extract_website(self, data: dict, company_name: str) -> Optional[str]:
        organic_results = data.get("organic", [])
        if not organic_results:
            return None
        
        company_lower = company_name.lower().replace(" ", "")
        
        for result in organic_results[:3]:
            link = result.get("link", "")
            domain = self._extract_domain(link)
            
            if not domain:
                continue
            
            domain_clean = domain.lower().replace("-", "").replace(".", "")
            if company_lower in domain_clean or domain_clean in company_lower:
                self.logger.debug(f"Found matching website: {link}")
                return link
        
        first_result = organic_results[0].get("link")
        self.logger.debug(f"Using first result as fallback: {first_result}")
        return first_result
    
    def _extract_contacts(self, data: dict) -> SerperContact:
        emails = set()
        phones = set()
        
        organic_results = data.get("organic", [])
        for result in organic_results[:5]:
            snippet = result.get("snippet", "")
            title = result.get("title", "")
            text = f"{title} {snippet}"
            
            found_emails = self.email_pattern.findall(text)
            emails.update(found_emails)
            
            found_phones = self.phone_pattern.findall(text)
            phones.update(found_phones)
        
        emails_list = [e for e in emails if self._is_valid_email(e)]
        phones_list = [p for p in phones if self._is_valid_phone(p)]
        
        confidence = 0.0
        if emails_list:
            confidence += 0.5
        if phones_list:
            confidence += 0.5
        
        return SerperContact(
            emails=emails_list,
            phones=phones_list,
            confidence=confidence
        )
    
    def _extract_domain(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None
    
    def _is_valid_email(self, email: str) -> bool:
        email_lower = email.lower()
        
        invalid_domains = [
            'example.com', 'test.com', 'placeholder.com',
            'google.com', 'facebook.com', 'twitter.com',
            'linkedin.com', 'youtube.com', 'instagram.com'
        ]
        
        for domain in invalid_domains:
            if email_lower.endswith(domain):
                return False
        
        if email_lower.startswith(('noreply@', 'no-reply@', 'info@example')):
            return False
        
        return True
    
    def _is_valid_phone(self, phone: str) -> bool:
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) < 10 or len(digits) > 11:
            return False
        
        if digits.startswith('1') and len(digits) == 11:
            return True
        elif len(digits) == 10:
            return True
        
        return False
    
    def discovery_search(self, query: str, num_results: int = 10) -> dict:
        self.logger.debug(f"Serper discovery query: {query}")
        
        try:
            response = requests.post(
                self.base_url,
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json={"q": query, "num": num_results},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Serper discovery API error: {e}")
            return {"organic": []}
    
    def places_search(self, query: str, num_results: int = 10, location: Optional[str] = None, gl: Optional[str] = None) -> dict:
        self.logger.debug(f"Serper places query: {query}")
        
        try:
            payload = {"q": query, "num": num_results}
            
            if location:
                payload["location"] = location
                self.logger.debug(f"  Location filter: {location}")
            
            if gl:
                payload["gl"] = gl
                self.logger.debug(f"  Country code (gl): {gl}")
            
            response = requests.post(
                self.places_url,
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Serper places API error: {e}")
            return {"places": []}
