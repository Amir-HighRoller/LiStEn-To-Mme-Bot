from abc import ABC, abstractmethod
from typing import Any


class MusicCatalogProvider(ABC):
    """
    Base interface for music catalog providers.

    Catalog providers are responsible for searching
    and retrieving music metadata from external catalogs.

    They are intentionally separate from
    MusicRecognitionProvider.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
    ) -> list[Any]:
        """
        Search the music catalog.

        Args:
            query: Song title, artist name, or other search text.

        Returns:
            A list of catalog results.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_info(
        self,
        item_id: str,
    ) -> Any | None:
        """
        Get detailed information about a catalog item.

        Args:
            item_id: Provider-specific item identifier.

        Returns:
            Catalog item information, or None if not found.
        """
        raise NotImplementedError