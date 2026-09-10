from __future__ import annotations

import base64
import hashlib
import hmac
import time
from pathlib import Path
from typing import Optional

import aiohttp

from config import (
    ACR_ACCESS_KEY,
    ACR_ACCESS_SECRET,
    ACR_HOST,
)
from core.providers import (
    MusicMatch,
    MusicRecognitionProvider,
)


class ACRCloudProvider(MusicRecognitionProvider):
    API_PATH = "/v1/identify"

    TIMEOUT_SECONDS = 60

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

        sample_bytes = path.stat().st_size
        timestamp = int(time.time())

        data_type = "audio"
        signature_version = "1"

        string_to_sign = (
            "POST\n"
            f"{self.API_PATH}\n"
            f"{ACR_ACCESS_KEY}\n"
            f"{data_type}\n"
            f"{signature_version}\n"
            f"{timestamp}"
        )

        signature = base64.b64encode(
            hmac.new(
                ACR_ACCESS_SECRET.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        url = (
            f"https://{ACR_HOST}"
            f"{self.API_PATH}"
        )

        form = aiohttp.FormData()

        form.add_field(
            "access_key",
            ACR_ACCESS_KEY,
        )

        form.add_field(
            "sample_bytes",
            str(sample_bytes),
        )

        form.add_field(
            "timestamp",
            str(timestamp),
        )

        form.add_field(
            "signature",
            signature,
        )

        form.add_field(
            "data_type",
            data_type,
        )

        form.add_field(
            "signature_version",
            signature_version,
        )

        timeout = aiohttp.ClientTimeout(
            total=self.TIMEOUT_SECONDS
        )

        with path.open("rb") as audio_file:

            form.add_field(
                "sample",
                audio_file,
                filename=path.name,
                content_type="audio/mpeg",
            )

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.post(
                    url,
                    data=form,
                ) as response:

                    response_text = await response.text()

                    if response.status != 200:
                        raise RuntimeError(
                            "ACRCloud HTTP error "
                            f"{response.status}: "
                            f"{response_text}"
                        )

                    try:
                        result = await response.json(
                            content_type=None
                        )
                    except Exception as error:
                        raise RuntimeError(
                            "ACRCloud returned invalid JSON: "
                            f"{error}"
                        ) from error

        status = result.get("status") or {}

        status_code = status.get("code")
        status_message = status.get("msg")

        if status_code != 0:
            raise RuntimeError(
                "ACRCloud API error: "
                f"code={status_code}, "
                f"message={status_message}"
            )

        metadata = result.get("metadata") or {}

        # -----------------------------------------------------
        # ACRCloud recognition result
        # -----------------------------------------------------

        music_list = metadata.get("music") or []

        if not music_list:
            music_list = metadata.get("humming") or []

        if not music_list:
            return None

        # -----------------------------------------------------
        # Safely sort results by score
        # -----------------------------------------------------

        def score_of(item: dict) -> float:
            try:
                value = float(
                    item.get("score") or 0
                )
            except (TypeError, ValueError):
                return 0.0

            if value < 0:
                return 0.0

            if value > 100:
                return 100.0

            return value

        music_list = sorted(
            music_list,
            key=score_of,
            reverse=True,
        )

        best_match = music_list[0]

        # -----------------------------------------------------
        # Title
        # -----------------------------------------------------

        title = (
            best_match.get("title")
            or ""
        ).strip()

        if not title:
            return None

        # -----------------------------------------------------
        # Artists
        # -----------------------------------------------------

        artists = (
            best_match.get("artists")
            or []
        )

        artist_names: list[str] = []

        for artist_data in artists:

            if not isinstance(
                artist_data,
                dict,
            ):
                continue

            name = (
                artist_data.get("name")
                or ""
            ).strip()

            if name:
                artist_names.append(name)

        artist = ", ".join(
            artist_names
        )

        if not artist:
            artist = "Unknown"

        # -----------------------------------------------------
        # Album
        # -----------------------------------------------------

        album_info = (
            best_match.get("album")
            or {}
        )

        album = None

        if isinstance(
            album_info,
            dict,
        ):
            album = (
                album_info.get("name")
                or None
            )

        # -----------------------------------------------------
        # Confidence
        # -----------------------------------------------------

        score = score_of(best_match)

        # -----------------------------------------------------
        # Track IDs
        # -----------------------------------------------------

        acrid = (
            best_match.get("acrid")
            or None
        )

        external_ids = (
            best_match.get("external_ids")
            or {}
        )

        isrc = None

        if isinstance(
            external_ids,
            dict,
        ):
            isrc = (
                external_ids.get("isrc")
                or None
            )

        track_id = isrc or acrid

        # -----------------------------------------------------
        # YouTube URL
        # -----------------------------------------------------

        external_metadata = (
            best_match.get("external_metadata")
            or {}
        )

        youtube_data = (
            external_metadata.get("youtube")
            or {}
        )

        youtube_video_id = None

        if isinstance(
            youtube_data,
            dict,
        ):
            youtube_video_id = (
                youtube_data.get("vid")
                or None
            )

        youtube_url = None

        if youtube_video_id:
            youtube_url = (
                "https://www.youtube.com/watch?v="
                f"{youtube_video_id}"
            )

        return MusicMatch(
            title=title,
            artist=artist,
            album=album,
            confidence=score,
            provider="acrcloud",
            track_id=track_id,
            url=youtube_url,
            sample_index=sample_index,
        )