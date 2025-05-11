"""
DeepSeek service implementation using OpenAI

This module implements the DeepseekService class that uses OpenAI's API
instead of DeepSeek, which is no longer used.
"""

import os
import json
import logging
import aiohttp
import backoff
from typing import Optional, Dict, Any, List

# Set up logging
logger = logging.getLogger(__name__)

class DeepseekService:
    """Service for using OpenAI API for completions"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the DeepseekService with an API key"""
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        
        # Check for API key
        if not self.api_key:
            logger.warning("No OpenAI API key provided. DeepseekService will not work.")
        else:
            # Mask the API key for logging
            masked_key = f"sk-...{self.api_key[-4:]}" if len(self.api_key) > 8 else "sk-..."
            logger.info(f"DeepseekService initialized with API key: {masked_key}")
            
        # API configuration
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.timeout = aiohttp.ClientTimeout(total=60)  # 60 seconds timeout
        
        # Model mapping from DeepSeek to OpenAI models
        self.model_mapping = {
            "deepseek-chat": "gpt-3.5-turbo",
            "deepseek-coder": "gpt-4",
            "default": "gpt-3.5-turbo"
        }
    
    @backoff.on_exception(backoff.expo, 
                         (aiohttp.ClientError, json.JSONDecodeError), 
                         max_tries=3)
    async def generate_completion(self, 
                                 prompt: str, 
                                 model: str = "deepseek-chat", 
                                 temperature: float = 0.2,
                                 max_tokens: int = 1000) -> str:
        """
        Generate a completion using OpenAI API as a replacement for DeepSeek
        
        Args:
            prompt: The prompt to generate completion for
            model: The model name (will be mapped to OpenAI equivalent)
            temperature: Control randomness (0-1)
            max_tokens: Maximum tokens to generate
            
        Returns:
            The generated text
        """
        if not self.api_key:
            logger.error("Cannot generate completion: No OpenAI API key available")
            return "Error: OpenAI API key not configured"
            
        try:
            # Map DeepSeek model to OpenAI model
            openai_model = self.model_mapping.get(model, self.model_mapping["default"])
            logger.info(f"Using OpenAI model {openai_model} (mapped from {model})")
            
            # Prepare request payload
            payload = {
                "model": openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            logger.info(f"Sending request to OpenAI API with prompt length: {len(prompt)}")
            
            # Send request to OpenAI API
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(self.api_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error ({response.status}): {error_text}")
                        return f"Error: OpenAI API returned status code {response.status}"
                    
                    # Parse response
                    response_data = await response.json()
                    
                    # Extract content from response
                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        content = response_data["choices"][0]["message"]["content"]
                        logger.info(f"Successfully generated completion (length: {len(content)})")
                        return content
                    else:
                        logger.error(f"Unexpected response format from OpenAI: {response_data}")
                        return "Error: Unexpected response format from OpenAI API"
                    
        except Exception as e:
            logger.exception(f"Error generating completion: {str(e)}")
            return f"Error generating completion: {str(e)}" 