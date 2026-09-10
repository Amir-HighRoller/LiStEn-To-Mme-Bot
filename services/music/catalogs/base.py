from abc import ABC, abstractmethod
from typing import Optional


class MusicCatalogProvider(ABC):
    """
    Base class for music catalog providers.

    A catalog provider is different from a recognition provider.

    Recognition Provider:
        Detects music from audio.

    Catalog Provider:
        Searches music metadata and music catalogs.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Search for music.

        Returns a list of normalized music dictionaries.
        """

        raise NotImplementedError

    @abstractmethod
    async def get_track(
        self,
        track_id: str,
    ) -> Optional[dict]:
        """
        Get information about a specific track.
        """

        raise NotImplementedError