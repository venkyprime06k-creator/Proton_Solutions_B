import httpx
import json
from typing import List, Dict, Any, AsyncGenerator
from groq import AsyncGroq
from openai import AsyncOpenAI
from app.config.settings import settings

class AIService:
    def __init__(self):
        self.groq_client = AsyncGroq(api_key=settings.groq_api_key) if settings.groq_api_key else None
        self.openrouter_api_key = settings.openrouter_api_key
        
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        custom_keys: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Generate chat completion using configured provider or user-supplied custom API keys"""
        
        provider = provider or settings.default_ai_provider
        custom_keys = custom_keys or {}
        
        # 1. Custom Keys & fallbacks configuration
        groq_key = custom_keys.get("groq")
        openai_key = custom_keys.get("openai")
        gemini_key = custom_keys.get("gemini")
        anthropic_key = custom_keys.get("anthropic")
        
        # Fallback logic for Groq
        if provider == "groq" and not groq_key and not self.groq_client:
            if self.openrouter_api_key:
                provider = "openrouter"
                model = "meta-llama/llama-3.2-3b-instruct:free"
            else:
                raise ValueError("Groq provider is selected but no Groq API key is available, and no OpenRouter key is configured for fallback.")
                
        # Fallback logic for OpenAI
        if provider == "openai" and not openai_key and not settings.openai_api_key:
            if self.openrouter_api_key:
                provider = "openrouter"
                model = "meta-llama/llama-3.3-70b-instruct:free"
            else:
                raise ValueError("OpenAI provider is selected but no OpenAI key is configured, and no OpenRouter key is available for fallback.")
                
        # Fallback logic for Gemini
        if provider == "gemini" and not gemini_key:
            if self.openrouter_api_key:
                provider = "openrouter"
                model = "google/gemini-2.5-flash:free"
            else:
                raise ValueError("Gemini provider is selected but no Gemini key is configured, and no OpenRouter key is available for fallback.")
                
        # Fallback logic for Anthropic
        if provider == "anthropic" and not anthropic_key:
            if self.openrouter_api_key:
                provider = "openrouter"
                model = "meta-llama/llama-3.3-70b-instruct:free"
            else:
                raise ValueError("Anthropic provider is selected but no Anthropic key is configured, and no OpenRouter key is available for fallback.")
        
        # 2. Execution based on provider
        if provider == "groq":
            client = AsyncGroq(api_key=groq_key) if groq_key else self.groq_client
            response = await client.chat.completions.create(
                model=model or "llama-3.1-8b-instant",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return {
                "id": response.id,
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "provider": "groq"
            }
            
        elif provider == "openai":
            key = openai_key or settings.openai_api_key
            client = AsyncOpenAI(api_key=key)
            response = await client.chat.completions.create(
                model=model or "gpt-4o-mini",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return {
                "id": response.id,
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "provider": "openai"
            }
            
        elif provider == "gemini":
            client = AsyncOpenAI(api_key=gemini_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            response = await client.chat.completions.create(
                model=model or "gemini-1.5-flash",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return {
                "id": response.id,
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                },
                "provider": "gemini"
            }
            
        elif provider == "anthropic":
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": model or "claude-3-5-sonnet-20241022",
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    },
                    timeout=60.0
                )
                if response.status_code != 200:
                    raise RuntimeError(f"Anthropic API error: {response.text}")
                data = response.json()
                return {
                    "id": data.get("id"),
                    "content": data["content"][0]["text"],
                    "model": data.get("model"),
                    "usage": data.get("usage", {}),
                    "provider": "anthropic"
                }
                
        elif provider == "openrouter":
            if not self.openrouter_api_key:
                raise ValueError("OpenRouter provider is selected but OPENROUTER_API_KEY is not configured in environment variables.")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model or "meta-llama/llama-3.3-70b-instruct:free",
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    try:
                        err_data = response.json()
                        err_msg = err_data.get("error", {}).get("message", "Unknown OpenRouter API error")
                    except Exception:
                        err_msg = f"HTTP {response.status_code} error"
                    raise RuntimeError(f"OpenRouter API error: {err_msg}")
                    
                data = response.json()
                if "error" in data:
                    raise RuntimeError(f"OpenRouter API error: {data['error'].get('message', data['error'])}")
                    
                return {
                    "id": data.get("id"),
                    "content": data["choices"][0]["message"]["content"],
                    "model": data.get("model"),
                    "usage": data.get("usage", {}),
                    "provider": "openrouter"
                }
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        provider: str = None,
        model: str = None,
        custom_keys: Dict[str, str] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion using configured provider or user-supplied custom API keys"""
        
        provider = provider or settings.default_ai_provider
        custom_keys = custom_keys or {}
        
        # 1. Custom Keys & fallbacks configuration
        groq_key = custom_keys.get("groq")
        openai_key = custom_keys.get("openai")
        gemini_key = custom_keys.get("gemini")
        anthropic_key = custom_keys.get("anthropic")
        
        # Fallback logic for Groq
        if provider == "groq" and not groq_key and not self.groq_client:
            if self.openrouter_api_key:
                provider = "openrouter"
                model = "meta-llama/llama-3.2-3b-instruct:free"
            else:
                raise ValueError("Groq provider is selected but no Groq API key is available, and no OpenRouter key is available for fallback.")
                
        # Fallback logic for OpenAI
        if provider == "openai" and not openai_key and not settings.openai_api_key:
            if self.openrouter_api_key:
                provider = "openrouter"
                model = "meta-llama/llama-3.3-70b-instruct:free"
            else:
                raise ValueError("OpenAI provider is selected but no OpenAI key is configured, and no OpenRouter key is available for fallback.")
                
        # Fallback logic for Gemini
        if provider == "gemini" and not gemini_key:
            if self.openrouter_api_key:
                provider = "openrouter"
                model = "google/gemini-2.5-flash:free"
            else:
                raise ValueError("Gemini provider is selected but no Gemini key is configured, and no OpenRouter key is available for fallback.")
                
        # Fallback logic for Anthropic
        if provider == "anthropic" and not anthropic_key:
            if self.openrouter_api_key:
                provider = "openrouter"
                model = "meta-llama/llama-3.3-70b-instruct:free"
            else:
                raise ValueError("Anthropic provider is selected but no Anthropic key is configured, and no OpenRouter key is available for fallback.")
        
        # 2. Execution based on provider
        if provider == "groq":
            client = AsyncGroq(api_key=groq_key) if groq_key else self.groq_client
            stream = await client.chat.completions.create(
                model=model or "llama-3.1-8b-instant",
                messages=messages,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        elif provider == "openai":
            key = openai_key or settings.openai_api_key
            client = AsyncOpenAI(api_key=key)
            stream = await client.chat.completions.create(
                model=model or "gpt-4o-mini",
                messages=messages,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        elif provider == "gemini":
            client = AsyncOpenAI(api_key=gemini_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            stream = await client.chat.completions.create(
                model=model or "gemini-1.5-flash",
                messages=messages,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        elif provider == "anthropic":
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": model or "claude-3-5-sonnet-20241022",
                        "messages": messages,
                        "max_tokens": 4096,
                        "stream": True
                    },
                    timeout=60.0
                ) as response:
                    if response.status_code != 200:
                        await response.aread()
                        raise RuntimeError(f"Anthropic API error: {response.text}")
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            event_data = line[5:].strip()
                            if event_data == "[DONE]":
                                break
                            try:
                                parsed = json.loads(event_data)
                                if parsed.get("type") == "content_block_delta":
                                    delta = parsed.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        yield delta.get("text", "")
                            except Exception:
                                pass
                                
        elif provider == "openrouter":
            if not self.openrouter_api_key:
                raise ValueError("OpenRouter provider is selected but OPENROUTER_API_KEY is not configured in environment variables.")
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model or "meta-llama/llama-3.3-70b-instruct:free",
                        "messages": messages,
                        "stream": True
                    },
                    timeout=60.0
                ) as response:
                    if response.status_code != 200:
                        await response.aread()
                        try:
                            err_data = response.json()
                            err_msg = err_data.get("error", {}).get("message", "Unknown OpenRouter API error")
                        except Exception:
                            err_msg = f"HTTP {response.status_code} error"
                        raise RuntimeError(f"OpenRouter API error: {err_msg}")
                        
                    async for line in response.aiter_lines():
                        if line.startswith("data: ") and line != "data: [DONE]":
                            import json
                            data = json.loads(line[6:])
                            if "error" in data:
                                raise RuntimeError(f"OpenRouter API stream error: {data['error'].get('message', data['error'])}")
                            if data.get("choices") and data["choices"][0]["delta"].get("content"):
                                yield data["choices"][0]["delta"]["content"]
        else:
            raise ValueError(f"Unknown provider: {provider}")

# Singleton instance
ai_service = AIService()