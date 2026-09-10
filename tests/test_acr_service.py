import asyncio

from services.music.service import MusicRecognitionService
from services.music.acrcloud import ACRCloudProvider


async def main():
    service = MusicRecognitionService(
        providers=[
            ACRCloudProvider(),
        ]
    )

    result = await service.recognize(
        "downloads/acr_test.mp3"
    )

    print("SERVICE RESULT:", result)


if __name__ == "__main__":
    asyncio.run(main())
