from core.providers import MusicRecognitionProvider
from services.music.audd import AudDProvider


def get_music_providers() -> list[MusicRecognitionProvider]:
    return [
        AudDProvider(),
    ]