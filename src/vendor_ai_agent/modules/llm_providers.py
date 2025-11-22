"""Concrete LLM provider implementations."""
from __future__ import annotations

import logging
import os
from typing import Optional

from .tender_profiler import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI implementation of LLMProvider using cost-optimized models."""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        default_model: str = "gpt-5-mini",
        use_flex_tier: bool = False
    ):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            default_model: Default model to use (default: gpt-5-mini for cost optimization)
            use_flex_tier: Whether to use flex tier for 50% discount (adds latency)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Run: poetry add openai"
            )
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.default_model = default_model
        self.use_flex_tier = use_flex_tier
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def generate(self, prompt: str, response_format: Optional[str] = None, model: Optional[str] = None) -> str:
        """Generate response using OpenAI API.
        
        Args:
            prompt: The prompt to send to the model
            response_format: Optional format hint ("json" for JSON mode)
            model: Optional model override (uses default_model if not specified)
            
        Returns:
            Generated text response
        """
        # Use specified model or fall back to default
        target_model = model or self.default_model
        
        try:
            # Build request parameters
            params = {
                "model": target_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a JSON extractor. Output ONLY raw JSON. Do not include markdown ```json``` tags. Do not write conversational text. Be concise."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            }
            
            # Apply constraints for gpt-5-mini and gpt-5-nano
            if "mini" in target_model.lower() or "nano" in target_model.lower():
                params["max_completion_tokens"] = 2500
                self.logger.info("Applied GPT-5 mini/nano constraints: max_completion_tokens=2500")
            else:
                # Only non-mini/nano models support temperature control
                params["temperature"] = 0.1
            
            # Enable JSON mode if requested
            if response_format == "json":
                params["response_format"] = {"type": "json_object"}
            
            # Enable flex tier if configured (50% discount, slower)
            if self.use_flex_tier:
                params["store"] = True
                params["metadata"] = {"tier": "flex"}
            
            response = self.client.chat.completions.create(**params)
            
            content = response.choices[0].message.content
            
            # Log token usage for cost tracking
            usage = response.usage
            self.logger.debug(
                "OpenAI API call - Model: %s, Tokens: %d input / %d output",
                target_model,
                usage.prompt_tokens,
                usage.completion_tokens
            )
            
            return content
        
        except Exception as exc:
            self.logger.error("OpenAI API call failed: %s", exc)
            raise
