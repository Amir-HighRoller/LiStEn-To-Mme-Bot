import asyncio
from typing import Optional

import aiohttp

from .base import MusicCatalogProvider


class RadioJavanCatalogProvider(
    MusicCatalogProvider
):
    """
    Radio Javan music catalog provider.

    This provider does NOT recognize music from audio.

    Its job is:
    - Search Radio Javan catalog
    - Get track information
    - Normalize results
    """

    BASE_URL = (
        "https://api.majidapi.ir/music/radiojavan"
    )

    def __init__(
        self,
        timeout: int = 15,
    ):
        self.timeout = timeout

    async def _request(
        self,
        params: dict,
    ) -> dict:

        timeout = aiohttp.ClientTimeout(
            total=self.timeout
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(
                self.BASE_URL,
                params=params,
            ) as response:

                response.raise_for_status()

                return await response.json()

    # =====================================================
    # SEARCH
    # =====================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict]:

        if not query or not query.strip():
            return []

        try:

            data = await self._request(
                {
                    "action": "search",
                    "s": query.strip(),
                }
            )

            return self._normalize_search_results(
                data,
                limit,
            )

        except asyncio.TimeoutError:

            print(
                "RADIO JAVAN SEARCH TIMEOUT"
            )

            return []

        except aiohttp.ClientError as error:

            print(
                "RADIO JAVAN HTTP ERROR:",
                repr(error),
            )

            return []

        except Exception as error:

            print(
                "RADIO JAVAN SEARCH ERROR:",
                repr(error),
            )

            return []

    # =====================================================
    # GET TRACK
    # =====================================================

    async def get_track(
        self,
        track_id: str,
    ) -> Optional[dict]:

        if not track_id:
            return None

        try:

            data = await self._request(
                {
                    "action": "info",
                    "id": track_id,
                }
            )

            return self._normalize_track(
                data
            )

        except asyncio.TimeoutError:

            print(
                "RADIO JAVAN TRACK TIMEOUT"
            )

            return None

        except aiohttp.ClientError as error:

            print(
                "RADIO JAVAN TRACK HTTP ERROR:",
                repr(error),
            )

            return None

        except Exception as error:

            print(
                "RADIO JAVAN TRACK ERROR:",
                repr(error),
            )

            return None

    # =====================================================
    # NORMALIZE SEARCH RESULTS
    # =====================================================

    def _normalize_search_results(
        self,
        data: dict,
        limit: int,
    ) -> list[dict]:

        results = []

        if not isinstance(data, dict):
            return results

        possible_lists = []

        for key in (
            "results",
            "data",
            "songs",
            "tracks",
            "music",
        ):

            value = data.get(key)

            if isinstance(value, list):

                possible_lists = value

                break

            if isinstance(value, dict):

                for nested_key in (
                    "results",
                    "songs",
                    "tracks",
                    "music",
                ):

                    nested_value = value.get(
                        nested_key
                    )

                    if isinstance(
                        nested_value,
                        list,
                    ):

                        possible_lists = (
                            nested_value
                        )

                        break

        for item in possible_lists[:limit]:

            if not isinstance(item, dict):
                continue

            normalized = self._normalize_item(
                item
            )

            if normalized:
                results.append(
                    normalized
                )

        return results

    # =====================================================
    # NORMALIZE TRACK
    # =====================================================

    def _normalize_track(
        self,
        data: dict,
    ) -> Optional[dict]:

        if not isinstance(data, dict):
            return None

        possible_item = data

        if isinstance(
            data.get("data"),
            dict,
        ):

            possible_item = data["data"]

        elif isinstance(
            data.get("result"),
            dict,
        ):

            possible_item = data["result"]

        elif isinstance(
            data.get("track"),
            dict,
        ):

            possible_item = data["track"]

        return self._normalize_item(
            possible_item
        )

    # =====================================================
    # NORMALIZE ITEM
    # =====================================================

    def _normalize_item(
        self,
        item: dict,
    ) -> Optional[dict]:

        if not isinstance(item, dict):
            return None

        track_id = self._first_value(
            item,
            [
                "id",
                "track_id",
                "song_id",
            ],
        )

        title = self._first_value(
            item,
            [
                "title",
                "name",
                "song",
            ],
        )

        artist = self._extract_artist(
            item
        )

        album = self._extract_album(
            item
        )

        image = self._first_value(
            item,
            [
                "image",
                "cover",
                "artwork",
                "thumbnail",
                "photo",
            ],
        )

        url = self._first_value(
            item,
            [
                "url",
                "link",
                "share_url",
            ],
        )

        if not title and not artist:
            return None

        return {
            "id": str(track_id)
            if track_id is not None
            else None,

            "title": title,

            "artist": artist,

            "album": album,

            "image": image,

            "url": url,

            "source": "radiojavan",
        }

    # =====================================================
    # HELPERS
    # =====================================================

    def _first_value(
        self,
        data: dict,
        keys: list[str],
    ):

        for key in keys:

            value = data.get(key)

            if value is not None:

                return value

        return None

    def _extract_artist(
        self,
        item: dict,
    ):

        artist = self._first_value(
            item,
            [
                "artist",
                "artist_name",
                "singer",
            ],
        )

        if isinstance(artist, dict):

            return self._first_value(
                artist,
                [
                    "name",
                    "title",
                ],
            )

        if isinstance(artist, list):

            names = []

            for value in artist:

                if isinstance(value, dict):

                    name = self._first_value(
                        value,
                        [
                            "name",
                            "title",
                        ],
                    )

                    if name:
                        names.append(
                            str(name)
                        )

                elif value:

                    names.append(
                        str(value)
                    )

            return ", ".join(names)

        return artist

    def _extract_album(
        self,
        item: dict,
    ):

        album = item.get("album")

        if isinstance(album, dict):

            return self._first_value(
                album,
                [
                    "title",
                    "name",
                ],
            )

        if album:
            return album

        return self._first_value(
            item,
            [
                "album_name",
            ],
        )