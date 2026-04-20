"""MiniMax API client for music generation.

Integrates with MiniMax's music-2.6 model to generate custom music.
API endpoint: https://api.minimaxi.com/v1/music_generation

Key characteristics:
- Synchronous API (no task polling needed)
- Returns audio as hex-encoded string or URL
- status: 1 = processing, 2 = completed
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger("minimax-client")

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_API_BASE = os.environ.get(
    "MINIMAX_API_BASE", "https://api.minimaxi.com"
)
MINIMAX_MODEL_ID = os.environ.get("MINIMAX_MODEL_ID", "music-2.6")


class MiniMaxClient:
    """Client for interacting with MiniMax's music generation API."""

    def __init__(
        self,
        api_key: str = MINIMAX_API_KEY,
        base_url: str = MINIMAX_API_BASE,
        model: str = MINIMAX_MODEL_ID,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=180.0,  # Music generation can take time
        )

    async def generate_music(
        self,
        prompt: str,
        lyrics: str = "",
        instrumental: bool = False,
        duration: int = 60,
        output_format: str = "url",
    ) -> dict[str, Any]:
        """Submit a music generation request.

        Args:
            prompt: Description of the music (style, mood, scene).
                Required for instrumental, length [1, 2000] chars.
                Optional for vocal music, length [0, 2000] chars.
            lyrics: Song lyrics with structure tags ([Verse], [Chorus], etc.).
                Required for vocal music, length [1, 3500] chars.
                Not required for instrumental.
            instrumental: Whether to generate instrumental-only music.
                When True, lyrics is not required.
            duration: Target duration in seconds (informational, API decides).
            output_format: "url" (24h expiry) or "hex" (base64-like encoding).

        Returns:
            Dict with audio data and metadata.
        """
        # Build request payload
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "output_format": output_format,
        }

        # Handle lyrics and instrumental mode
        if instrumental:
            payload["is_instrumental"] = True
            if lyrics:
                # Allow lyrics with instrumental for hybrid cases
                payload["lyrics"] = lyrics
        else:
            if lyrics:
                payload["lyrics"] = lyrics
            else:
                # Enable lyrics auto-generation
                payload["lyrics_optimizer"] = True

        # Audio quality settings
        payload["audio_setting"] = {
            "sample_rate": 44100,
            "bitrate": 256000,
            "format": "mp3",
        }

        log.info(
            "Submitting music generation: model=%s, prompt=%s, instrumental=%s",
            self.model, prompt[:50], instrumental,
        )

        response = await self._client.post(
            "/v1/music_generation",
            json=payload,
        )
        response.raise_for_status()

        result = response.json()

        # Check for errors
        base_resp = result.get("base_resp", {})
        status_code = base_resp.get("status_code", -1)
        status_msg = base_resp.get("status_msg", "")

        if status_code != 0:
            raise RuntimeError(f"MiniMax API error ({status_code}): {status_msg}")

        data = result.get("data", {})
        extra_info = result.get("extra_info", {})

        # Parse response
        audio_data = data.get("audio", "")
        status = data.get("status", 0)

        return {
            "status": "completed" if status == 2 else "processing",
            "audio": audio_data,
            "output_format": output_format,
            "audio_url": audio_data if output_format == "url" else "",
            "audio_hex": audio_data if output_format == "hex" else "",
            "metadata": {
                "duration_ms": extra_info.get("music_duration"),
                "sample_rate": extra_info.get("music_sample_rate"),
                "channels": extra_info.get("music_channel"),
                "bitrate": extra_info.get("bitrate"),
                "file_size": extra_info.get("music_size"),
            },
            "trace_id": result.get("trace_id", ""),
        }

    async def generate_and_wait(
        self,
        prompt: str,
        lyrics: str = "",
        instrumental: bool = False,
        duration: int = 60,
        output_format: str = "url",
    ) -> dict[str, Any]:
        """Generate music and return the result.

        MiniMax API is synchronous, so this method just wraps generate_music.

        Args:
            prompt: Music description (style, mood, scene)
            lyrics: Optional lyrics with structure tags
            instrumental: Whether to generate instrumental-only
            duration: Target duration (informational)
            output_format: "url" or "hex"

        Returns:
            Dict with audio URL or hex data.
        """
        result = await self.generate_music(
            prompt=prompt,
            lyrics=lyrics,
            instrumental=instrumental,
            duration=duration,
            output_format=output_format,
        )

        # Check if still processing (shouldn't happen with sync API)
        if result["status"] == "processing":
            raise RuntimeError(
                "Music generation returned processing status. "
                "This shouldn't happen with the synchronous API."
            )

        return result

    def hex_to_bytes(self, hex_str: str) -> bytes:
        """Convert hex-encoded audio to bytes.

        The API returns audio as a hex string when output_format="hex".
        This method converts it to raw bytes for file upload.
        """
        return bytes.fromhex(hex_str)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
