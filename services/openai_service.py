import time
import json
import os
from typing import Optional, Dict, Any
from openai import OpenAI
from config.settings import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_PRICING,
)


class OpenAIService:
    """Service for OpenAI API calls."""

    def __init__(self, agent_name: str = "GenericAgent"):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in .env file")

        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL
        self.agent_name = agent_name
        self.interview_id = os.getenv("CURRENT_INTERVIEW_ID")
        self.user_id = os.getenv("CURRENT_USER_ID", "system")

    def log_usage(self, usage: Dict, status: str = "success", error: str = None):
        """Log usage to database."""
        try:
            from database.usage_logger import UsageLogger
            UsageLogger.log_usage(
                agent_name=self.agent_name,
                model=usage.get("model", self.model),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                latency_ms=usage.get("latency_ms", 0),
                cost_usd=usage.get("cost_usd", 0),
                interview_id=os.getenv("CURRENT_INTERVIEW_ID") or self.interview_id,
                user_id=self.user_id,
                status=status,
                error_message=error,
            )
        except Exception as e:
            print(f"Usage logging failed: {e}")

    def call(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        system_prompt: str = None,
    ) -> str:
        """Make a call to OpenAI."""
        start_time = time.time()

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract response text
            content = response.choices[0].message.content

            # Get usage info
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "latency_ms": latency_ms,
                "model": self.model,
            }

            # Calculate cost
            pricing = OPENAI_PRICING.get(self.model, {})
            input_rate = pricing.get("input", 0)
            output_rate = pricing.get("output", 0)

            usage["cost_usd"] = (
                response.usage.prompt_tokens * input_rate +
                response.usage.completion_tokens * output_rate
            )

            # Log usage
            self.log_usage(usage, status="success")

            return content, usage

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            self.log_usage(
                {"model": self.model, "input_tokens": 0, "output_tokens": 0, "latency_ms": latency_ms, "cost_usd": 0},
                status="error", error=str(e)[:300],
            )
            raise Exception(f"OpenAI API error: {str(e)}, Latency: {latency_ms}ms")

    def call_json(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        system_prompt: str = None,
    ) -> Dict[str, Any]:
        """Make a call expecting JSON response."""
        response_text, usage = self.call(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )

        try:
            # Try to parse JSON
            response_json = json.loads(response_text)
            return response_json, usage
        except json.JSONDecodeError:
            # Try to extract JSON from text
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                try:
                    response_json = json.loads(json_str)
                    return response_json, usage
                except json.JSONDecodeError:
                    raise ValueError(f"Could not parse JSON from response: {response_text}")
            else:
                raise ValueError(f"No JSON found in response: {response_text}")
