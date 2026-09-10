from __future__ import annotations

import subprocess
import uuid
from pathlib import Path


# ============================================================
# SETTINGS
# ============================================================

SAMPLE_DIR = (
    Path("downloads")
    / "samples"
)

SAMPLE_DURATION = 15

MAX_SAMPLES = 6

SAMPLE_BITRATE = "128k"

SAMPLE_RATE = 44100

SAMPLE_CHANNELS = 2


SAMPLE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# CHECK FFMPEG
# ============================================================

def check_ffmpeg() -> None:

    for command_name in (
        "ffmpeg",
        "ffprobe",
    ):

        try:

            result = subprocess.run(
                [
                    command_name,
                    "-version",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        except FileNotFoundError as error:

            raise RuntimeError(
                f"{command_name} روی سیستم نصب نیست."
            ) from error

        if result.returncode != 0:

            raise RuntimeError(
                f"{command_name} قابل اجرا نیست."
            )


# ============================================================
# GET DURATION
# ============================================================

def get_audio_duration(
    audio_path: str | Path,
) -> float:

    audio_path = Path(
        audio_path
    )

    if not audio_path.exists():
        raise FileNotFoundError(
            f"فایل صوتی پیدا نشد: {audio_path}"
        )

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode != 0:

        raise RuntimeError(
            "FFprobe نتوانست مدت فایل صوتی را تشخیص دهد."
        )

    output = result.stdout.strip()

    if not output:

        raise RuntimeError(
            "مدت فایل صوتی دریافت نشد."
        )

    try:

        duration = float(output)

    except ValueError as error:

        raise RuntimeError(
            f"مدت فایل صوتی نامعتبر است: {output}"
        ) from error

    if duration <= 0:
        return 0.0

    return duration


# ============================================================
# SAMPLE START TIMES
# ============================================================

def calculate_sample_starts(
    duration: float,
) -> list[float]:

    if duration <= 0:
        return []

    # --------------------------------------------------------
    # فایل تا 15 ثانیه
    # --------------------------------------------------------

    if duration <= SAMPLE_DURATION:
        return [0.0]

    max_start = max(
        0.0,
        duration - SAMPLE_DURATION,
    )

    # --------------------------------------------------------
    # فایل‌های 15 تا 30 ثانیه
    # --------------------------------------------------------

    if duration <= 30:

        candidates = [
            0.0,
            max_start,
        ]

    # --------------------------------------------------------
    # فایل‌های 30 تا 60 ثانیه
    # --------------------------------------------------------

    elif duration <= 60:

        candidates = [
            0.0,
            duration * 0.25,
            duration * 0.50,
            duration * 0.75,
            max_start,
        ]

    # --------------------------------------------------------
    # فایل‌های بلند
    # --------------------------------------------------------

    else:

        percentages = [
            0.10,
            0.25,
            0.40,
            0.55,
            0.70,
            0.85,
        ]

        candidates = [
            duration * percentage
            for percentage in percentages
        ]

    # --------------------------------------------------------
    # Clamp + deduplicate
    # --------------------------------------------------------

    starts: list[float] = []

    for value in candidates:

        start = max(
            0.0,
            min(
                float(value),
                max_start,
            ),
        )

        start = round(
            start,
            3,
        )

        if start not in starts:
            starts.append(start)

    return starts[:MAX_SAMPLES]


# ============================================================
# CREATE ONE SAMPLE
# ============================================================

def create_sample(
    audio_path: str | Path,
    start_time: float,
    index: int,
) -> Path:

    audio_path = Path(
        audio_path
    )

    if not audio_path.exists():
        raise FileNotFoundError(
            f"فایل صوتی پیدا نشد: {audio_path}"
        )

    SAMPLE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    job_id = uuid.uuid4().hex

    output_path = (
        SAMPLE_DIR
        / (
            f"{audio_path.stem}_"
            f"{job_id}_"
            f"sample_{index}.mp3"
        )
    )

    command = [
        "ffmpeg",
        "-y",

        "-ss",
        str(start_time),

        "-i",
        str(audio_path),

        "-t",
        str(SAMPLE_DURATION),

        "-vn",

        "-ar",
        str(SAMPLE_RATE),

        "-ac",
        str(SAMPLE_CHANNELS),

        "-codec:a",
        "libmp3lame",

        "-b:a",
        SAMPLE_BITRATE,

        "-loglevel",
        "error",

        str(output_path),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode != 0:

        raise RuntimeError(
            "ساخت sample ناموفق بود: "
            f"{result.stderr.strip()}"
        )

    if not output_path.exists():

        raise RuntimeError(
            f"sample ساخته نشد: {output_path}"
        )

    if output_path.stat().st_size <= 0:

        output_path.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            f"sample خالی است: {output_path}"
        )

    return output_path


# ============================================================
# CREATE SAMPLES
# ============================================================

def create_samples(
    audio_path: str | Path,
) -> list[Path]:

    audio_path = Path(
        audio_path
    )

    if not audio_path.exists():
        raise FileNotFoundError(
            f"فایل صوتی پیدا نشد: {audio_path}"
        )

    check_ffmpeg()

    duration = get_audio_duration(
        audio_path
    )

    print(
        "AUDIO DURATION:",
        round(duration, 2),
        "seconds",
    )

    if duration <= 0:

        raise RuntimeError(
            "مدت فایل صوتی صفر یا نامعتبر است."
        )

    start_times = calculate_sample_starts(
        duration
    )

    print(
        "SAMPLE START TIMES:",
        start_times,
    )

    samples: list[Path] = []

    for index, start_time in enumerate(
        start_times,
        start=1,
    ):

        try:

            sample_path = create_sample(
                audio_path=audio_path,
                start_time=start_time,
                index=index,
            )

            samples.append(
                sample_path
            )

            print(
                f"SAMPLE CREATED [{index}]:",
                sample_path,
            )

        except Exception as error:

            print(
                f"SAMPLE ERROR [{index}] "
                f"at {start_time}s:",
                repr(error),
            )

    return samples


# ============================================================
# CLEANUP
# ============================================================

def cleanup_samples(
    samples: list[str | Path],
) -> None:

    for sample in samples:

        try:

            path = Path(sample)

            if path.exists():

                path.unlink(
                    missing_ok=True
                )

        except Exception as error:

            print(
                "SAMPLE CLEANUP ERROR:",
                repr(error),
            )


# ============================================================
# CLEAN OLD SAMPLES
# ============================================================

def cleanup_sample_directory() -> None:

    if not SAMPLE_DIR.exists():
        return

    for file_path in SAMPLE_DIR.iterdir():

        try:

            if file_path.is_file():
                file_path.unlink(
                    missing_ok=True
                )

        except Exception as error:

            print(
                "SAMPLE DIRECTORY CLEANUP ERROR:",
                repr(error),
            )