import asyncio

from core.providers import MusicMatch, MusicRecognitionProvider
from services.music.service import MusicRecognitionService


class FailingProvider(MusicRecognitionProvider):
    async def recognize(self, audio_path: str):
        raise RuntimeError("Provider 1 failed")


class WorkingProvider(MusicRecognitionProvider):
    async def recognize(self, audio_path: str):
        return MusicMatch(
            title="Test Song",
            artist="Test Artist",
            provider="working-provider",
            confidence=0.95,
        )


async def run_test():
    service = MusicRecognitionService(
        providers=[
            FailingProvider(),
            WorkingProvider(),
        ]
    )

    result = await service.recognize("test.mp3")

    assert result is not None
    assert result.title == "Test Song"
    assert result.artist == "Test Artist"
    assert result.provider == "working-provider"
    assert result.confidence == 0.95

    print("MUSIC SERVICE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(run_test())