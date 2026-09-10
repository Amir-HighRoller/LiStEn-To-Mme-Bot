from __future__ import annotations

from pathlib import Path
from typing import Optional

import aiohttp

from config import AUDD_TOKEN
from core.providers import (
    MusicMatch,
    MusicRecognitionProvider,
)


class AudDProvider(MusicRecognitionProvider):
    API_URL = "https://api.audd.io/"

    TIMEOUT_SECONDS = 120

    async def recognize(
        self,
        audio_path: str,
        sample_index: Optional[int] = None,
    ) -> Optional[MusicMatch]:

        path = Path(audio_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {path}"
            )

        if path.stat().st_size <= 0:
            raise ValueError(
                f"Audio file is empty: {path}"
            )

        if not AUDD_TOKEN:
            raise RuntimeError(
                "AUDD_TOKEN is not configured."
            )

        data = aiohttp.FormData()

        data.add_field(
            "api_token",
            AUDD_TOKEN,
        )

        timeout = aiohttp.ClientTimeout(
            total=self.TIMEOUT_SECONDS
        )

        with path.open("rb") as audio_file:

            data.add_field(
                "file",
                audio_file,
                filename=path.name,
                content_type="audio/mpeg",
            )

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.post(
                    self.API_URL,
                    data=data,
                ) as response:

                    response_text = await response.text()

                    if response.status != 200:
                        raise RuntimeError(
                            "AudD HTTP error "
                            f"{response.status}: "
                            f"{response_text}"
                        )

                    try:
                        result = await response.json(
                            content_type=None
                        )
                    except Exception as error:
                        raise RuntimeError(
                            "AudD returned invalid JSON: "
                            f"{error}"
                        ) from error

        if result.get("status") != "success":
            raise RuntimeError(
                "AudD API error: "
                f"{result}"
            )

        track = result.get("result")

        if not track:
            return None

        if not isinstance(
            track,
            dict,
        ):
            return None

        title = (
            track.get("title")
            or ""
        ).strip()

        artist = (
            track.get("artist")
            or ""
        ).strip()

        if not title or not artist:
            return None

        album = (
            track.get("album")
            or None
        )

        song_link = (
            track.get("song_link")
            or None
        )

        return MusicMatch(
            title=title,
            artist=artist,
            album=album,
            confidence=None,
            provider="audd",
            track_id=song_link,
            url=song_link,
            sample_index=sample_index,
        )