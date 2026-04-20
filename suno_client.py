"""Suno API client for music generation.

Integrates with Suno's API to generate custom music based on user prompts.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger("suno-client")

SUNO_API_BASE = os.environ.get("SUNO_API_BASE", "https://api.suno.com")
SUNO_API_KEY = os.environ.get("SUNO_API_KEY", "")


class SunoClient:
    """Client for interacting with Suno's music generation API."""

    def __init__(self, api_key: str = SUNO_API_KEY, base_url: str = SUNO_API_BASE):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,  # Music generation can take time
        )

    async def generate_music(
        self,
        prompt: str,
        style: str = "",
        duration: int = 60,
        instrumental: bool = False,
    ) -> dict[str, Any]:
        """Submit a music generation request.

        Args:
            prompt: Description of the music to generate (e.g., "a peaceful piano piece")
            style: Music style (e.g., "pop", "rock", "classical", "electronic")
            duration: Target duration in seconds (default 60)
            instrumental: Whether to generate instrumental-only music

        Returns:
            Dict containing the task ID and status for tracking.
        """
        payload = {
            "prompt": prompt,
            "style": style,
            "duration": duration,
            "instrumental": instrumental,
        }

        log.info("Submitting music generation request: %s", payload)

        response = await self._client.post("/api/generate", json=payload)
        response.raise_for_status()

        result = response.json()
        task_id = result.get("task_id") or result.get("id")

        return {
            "task_id": task_id,
            "status": result.get("status", "pending"),
            "estimated_time": result.get("estimated_time", 30),
        }

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Check the status of a music generation task.

        Args:
            task_id: The task ID returned by generate_music.

        Returns:
            Dict with task status and result URL if completed.
        """
        response = await self._client.get(f"/api/tasks/{task_id}")
        response.raise_for_status()

        return response.json()

    async def get_music_url(self, task_id: str) -> str:
        """Get the final music file URL after generation completes.

        Args:
            task_id: The task ID.

        Returns:
            URL to the generated music file.
        """
        status = await self.get_task_status(task_id)
        status_val = status.get("status", "").lower()

        if status_val != "completed":
            raise ValueError(f"Task not completed. Status: {status_val}")

        return status.get("audio_url") or status.get("url", "")

    async def generate_and_wait(
        self,
        prompt: str,
        style: str = "",
        duration: int = 60,
        instrumental: bool = False,
        poll_interval: int = 5,
        max_wait: int = 300,
    ) -> dict[str, Any]:
        """Generate music and wait for completion.

        Args:
            prompt: Music description
            style: Music style
            duration: Target duration
            instrumental: Instrumental only flag
            poll_interval: Seconds between status checks
            max_wait: Maximum wait time in seconds

        Returns:
            Dict with final result including audio URL.
        """
        result = await self.generate_music(
            prompt=prompt,
            style=style,
            duration=duration,
            instrumental=instrumental,
        )

        task_id = result["task_id"]
        elapsed = 0

        while elapsed < max_wait:
            await self._sleep(poll_interval)
            elapsed += poll_interval

            status = await self.get_task_status(task_id)
            status_val = status.get("status", "").lower()

            if status_val == "completed":
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "audio_url": status.get("audio_url") or status.get("url", ""),
                    "title": status.get("title", ""),
                    "metadata": status.get("metadata", {}),
                }
            elif status_val in ("failed", "error"):
                raise RuntimeError(
                    f"Music generation failed: {status.get('error', 'Unknown error')}"
                )

        raise TimeoutError(f"Music generation timed out after {max_wait}s")

    async def _sleep(self, seconds: int):
        """Non-blocking sleep."""
        import asyncio
        await asyncio.sleep(seconds)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
