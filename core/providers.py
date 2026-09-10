from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class MusicMatch:
    title: str
    artist: str

    album: Optional[str] = None
    confidence: Optional[float] = None

    provider: Optional[str] = None
    track_id: Optional[str] = None
    url: Optional[str] = None

    # ---------------------------------------------------------
    # Recognition context
    # ---------------------------------------------------------
    #
    # شماره‌ی sampleای که این نتیجه از آن به دست آمده.
    #
    # None یعنی provider خودش این اطلاعات را نداشته
    # یا نتیجه خارج از جریان multi-sample ساخته شده.
    #
    sample_index: Optional[int] = None


class MusicRecognitionProvider(ABC):

    @abstractmethod
    async def recognize(
        self,
        audio_path: str,
        sample_index: Optional[int] = None,
    ) -> Optional[MusicMatch]:
        """
        تشخیص موسیقی از فایل صوتی.

        Args:
            audio_path:
                مسیر sample صوتی.

            sample_index:
                شماره sample در جریان recognition.
                از 1 شروع می‌شود.

        Returns:
            MusicMatch:
                اگر آهنگ پیدا شد.

            None:
                اگر چیزی پیدا نشد.
        """
        raise NotImplementedError