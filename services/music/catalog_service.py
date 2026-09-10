from typing import Optional

from services.music.catalogs.base import MusicCatalogProvider
from services.music.catalogs.radiojavan import RadioJavanCatalogProvider


class CatalogService:
    """
    Main service for working with music catalog providers.

    This service acts as a central layer between the bot/application
    and individual music catalog providers.

    Providers can be added or removed without changing the rest
    of the application.
    """

    def __init__(
        self,
        providers: Optional[list[MusicCatalogProvider]] = None,
    ) -> None:
        """
        Initialize catalog providers.

        If no providers are supplied, the default providers
        will be loaded.
        """

        if providers is None:
            providers = [
                RadioJavanCatalogProvider(),
            ]

        self.providers = providers

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Search for music across all available catalog providers.

        Results are normalized by each provider.

        Duplicate tracks are removed.
        """

        if not query or not query.strip():
            return []

        query = query.strip()

        results: list[dict] = []

        for provider in self.providers:
            try:
                provider_results = await provider.search(
                    query=query,
                    limit=limit,
                )

                if provider_results:
                    results.extend(provider_results)

            except Exception:
                # One provider failing should not break
                # the entire catalog search.
                continue

        return self._remove_duplicates(results, limit)

    async def get_track(
        self,
        track_id: str,
        provider_name: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Get a track from catalog providers.

        If provider_name is supplied, only that provider
        will be queried.

        Otherwise all providers will be checked.
        """

        if not track_id:
            return None

        for provider in self.providers:

            if provider_name:
                current_provider_name = getattr(
                    provider,
                    "name",
                    provider.__class__.__name__.lower(),
                )

                if current_provider_name != provider_name:
                    continue

            try:
                track = await provider.get_track(track_id)

                if track:
                    return track

            except Exception:
                continue

        return None

    @staticmethod
    def _remove_duplicates(
        tracks: list[dict],
        limit: int,
    ) -> list[dict]:
        """
        Remove duplicate tracks.

        Deduplication priority:

        1. provider + id
        2. artist + title
        """

        unique_tracks: list[dict] = []

        seen: set[str] = set()

        for track in tracks:

            track_id = track.get("id")
            provider = track.get("provider")

            title = track.get("title", "")
            artist = track.get("artist", "")

            if track_id:
                key = f"{provider}:{track_id}"

            else:
                key = (
                    f"{provider}:"
                    f"{artist.lower().strip()}:"
                    f"{title.lower().strip()}"
                )

            if key in seen:
                continue

            seen.add(key)

            unique_tracks.append(track)

            if len(unique_tracks) >= limit:
                break

        return unique_tracks


# Default singleton instance
catalog_service = CatalogService()