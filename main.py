import asyncio
import re
import uuid
import subprocess

from pathlib import Path
from urllib.parse import quote_plus

import yt_dlp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from config import (
    BOT_TOKEN,
    ADMIN_USER_ID,
    validate_config,
)

from database import (
    init_database,
    get_music_reports,
)

from handlers import callbacks

from handlers.menu import (
    main_menu,
    music_result_keyboard,
    update_message_keyboard,
)

from handlers.states import (
    AudioExtractionState,
)

from services.music.service import (
    MusicRecognitionService,
)

from services.music.acrcloud import (
    ACRCloudProvider,
)

from services.music.audd import (
    AudDProvider,
)

from services.music.sampler import (
    create_samples,
)

from services.music.catalog_service import (
    CatalogService,
)

from services.music.catalogs.radiojavan import (
    RadioJavanCatalogProvider,
)


# ============================================================
# SETTINGS
# ============================================================

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 49 * 1024 * 1024


# ============================================================
# BOT
# ============================================================

bot = Bot(
    token=BOT_TOKEN,
)

dp = Dispatcher(
    storage=MemoryStorage(),
)

dp.include_router(
    callbacks.router
)


# ============================================================
# MUSIC RECOGNITION
# ============================================================

music_service = MusicRecognitionService(
    providers=[
        ACRCloudProvider(),
        AudDProvider(),
    ]
)


# ============================================================
# MUSIC CATALOG
# ============================================================

catalog_service = CatalogService(
    providers=[
        RadioJavanCatalogProvider(),
    ]
)


# ============================================================
# URL
# ============================================================

URL_PATTERN = re.compile(
    r"https?://[^\s]+",
    re.IGNORECASE,
)


def extract_url(text: str):
    match = URL_PATTERN.search(
        text or ""
    )

    if match:
        return match.group(0)

    return None


# ============================================================
# PLATFORM DETECTION
# ============================================================

def detect_platform(url: str) -> str:
    url_lower = url.lower()

    platforms = {
        "instagram": [
            "instagram.com",
            "instagr.am",
        ],
        "youtube": [
            "youtube.com",
            "youtu.be",
        ],
        "threads": [
            "threads.net",
        ],
        "x": [
            "twitter.com",
            "x.com",
        ],
        "tiktok": [
            "tiktok.com",
        ],
        "spotify": [
            "spotify.com",
            "open.spotify.com",
        ],
        "pinterest": [
            "pinterest.com",
            "pin.it",
        ],
        "radiojavan": [
            "radiojavan.com",
        ],
        "soundcloud": [
            "soundcloud.com",
        ],
        "deezer": [
            "deezer.com",
        ],
        "facebook": [
            "facebook.com",
            "fb.watch",
        ],
        "ifunny": [
            "ifunny.co",
        ],
        "snapchat": [
            "snapchat.com",
        ],
        "reddit": [
            "reddit.com",
            "redd.it",
        ],
        "tumblr": [
            "tumblr.com",
        ],
        "rumble": [
            "rumble.com",
        ],
        "imgur": [
            "imgur.com",
        ],
    }

    for platform, domains in platforms.items():
        if any(
            domain in url_lower
            for domain in domains
        ):
            return platform

    return "unknown"


# ============================================================
# VIDEO KEYBOARD
# ============================================================

def video_keyboard(
    video_filename: str,
) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎵 شناسایی موسیقی",
                    callback_data=(
                        f"recognize_music:"
                        f"{video_filename}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎧 استخراج صدای ویدیو",
                    callback_data=(
                        f"audio:"
                        f"{video_filename}"
                    ),
                )
            ],
        ]
    )


# ============================================================
# DOWNLOAD VIDEO FROM URL
# ============================================================

def download_video(url: str):

    job_id = uuid.uuid4().hex

    output_template = str(
        DOWNLOAD_DIR
        / f"{job_id}.%(ext)s"
    )

    options = {
        "outtmpl": output_template,
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:

        info = ydl.extract_info(
            url,
            download=True,
        )

    files = list(
        DOWNLOAD_DIR.glob(
            f"{job_id}.*"
        )
    )

    if not files:
        raise RuntimeError(
            "Video file was not created."
        )

    file_path = files[0]

    if file_path.stat().st_size > MAX_FILE_SIZE:

        file_path.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            "حجم ویدئو بیشتر از حد مجاز تلگرام است."
        )

    title = (
        info.get("title")
        or "Video"
    )

    return file_path, title


# ============================================================
# DOWNLOAD TELEGRAM VIDEO
# ============================================================

async def download_telegram_video(
    message: Message,
):

    if not message.video:
        raise RuntimeError(
            "No video found in message."
        )

    video = message.video

    file = await bot.get_file(
        video.file_id
    )

    if not file.file_path:
        raise RuntimeError(
            "Telegram file path was not found."
        )

    file_size = (
        video.file_size or 0
    )

    if file_size > MAX_FILE_SIZE:
        raise RuntimeError(
            "حجم ویدئو بیشتر از حد مجاز تلگرام است."
        )

    job_id = uuid.uuid4().hex

    video_path = (
        DOWNLOAD_DIR
        / f"{job_id}.mp4"
    )

    await bot.download_file(
        file.file_path,
        destination=str(video_path),
    )

    if not video_path.exists():
        raise RuntimeError(
            "Video file was not downloaded."
        )

    actual_size = (
        video_path.stat().st_size
    )

    if actual_size > MAX_FILE_SIZE:

        video_path.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            "حجم ویدئو بیشتر از حد مجاز تلگرام است."
        )

    return video_path


# ============================================================
# EXTRACT AUDIO
# ============================================================

def extract_audio(
    video_path: Path,
):

    audio_path = (
        video_path.with_suffix(".mp3")
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(audio_path),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:

        print(
            "FFMPEG ERROR:",
            result.stderr,
        )

        raise RuntimeError(
            "FFmpeg could not extract audio."
        )

    if not audio_path.exists():
        raise RuntimeError(
            "Audio file was not created."
        )

    if audio_path.stat().st_size > MAX_FILE_SIZE:

        audio_path.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            "حجم فایل صوتی بیشتر از حد مجاز است."
        )

    return audio_path


# ============================================================
# ADMIN HELPERS
# ============================================================

def is_admin(
    message: Message,
) -> bool:

    return (
        message.from_user is not None
        and message.from_user.id == ADMIN_USER_ID
    )


def split_text(
    text: str,
    max_length: int = 3900,
):

    chunks = []

    while len(text) > max_length:

        split_at = text.rfind(
            "\n",
            0,
            max_length,
        )

        if split_at <= 0:
            split_at = max_length

        chunks.append(
            text[:split_at]
        )

        text = text[
            split_at:
        ].lstrip()

    if text:
        chunks.append(text)

    return chunks


# ============================================================
# /START
# ============================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
):

    text = (
        "سلام 👋\n\n"
        "به *LiStEn_To_Mme* خوش اومدی.\n\n"
        "🎵 برای شناسایی موسیقی، "
        "ویدیو یا فایل صوتی خودت رو ارسال کن.\n\n"
        "یا از منوی زیر استفاده کن."
    )

    await message.answer(
        text,
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# /ADMIN
# ============================================================

ADMIN_COMMAND_PATTERN = re.compile(
    r"^/admin(?:@\w+)?$",
    re.IGNORECASE,
)


@dp.message(
    F.text.regexp(ADMIN_COMMAND_PATTERN)
)
async def admin_handler(
    message: Message,
):
    print(
        "ADMIN COMMAND RECEIVED:",
        message.from_user.id
        if message.from_user
        else None,
    )

    if not is_admin(message):
        await message.answer(
            "⛔ دسترسی به پنل مدیریت ندارید."
        )
        return

    try:
        reports = get_music_reports(limit=50)

    except Exception as error:
        print(
            "ADMIN REPORT ERROR:",
            repr(error),
        )

        await message.answer(
            "❌ خطا در دریافت گزارش‌ها."
        )

        return

    if not reports:
        await message.answer(
            "📭 هنوز هیچ گزارشی برای «آهنگ اشتباه» ثبت نشده است."
        )

        return

    text = "🛠 پنل مدیریت\n\n"
    text += "🎵 گزارش‌های «آهنگ اشتباه»:\n\n"

    for report in reports:
        text += (
            f"🆔 گزارش: {report['id']}\n"
            f"👤 User ID: {report['user_id']}\n"
            f"📛 Username: @{report['username'] or '-'}\n"
            f"🎵 Track ID: {report['track_id']}\n"
            f"🕐 زمان: {report['created_at']}\n"
            "──────────────────\n"
        )

    for i in range(0, len(text), 4000):
        await message.answer(
            text[i:i + 4000]
        )
# ============================================================
# /LANG
# ============================================================

@dp.message(
    F.text == "/lang"
)
async def language_handler(
    message: Message,
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇮🇷 فارسی",
                    callback_data="lang:fa",
                ),
                InlineKeyboardButton(
                    text="🇬🇧 English",
                    callback_data="lang:en",
                ),
            ]
        ]
    )

    await message.answer(
        "🌐 زبان موردنظر خودت رو انتخاب کن:",
        reply_markup=keyboard,
    )


# ============================================================
# LANGUAGE CALLBACK
# ============================================================

@dp.callback_query(
    F.data.startswith("lang:")
)
async def language_callback(
    callback: CallbackQuery,
):

    language = callback.data.split(
        ":",
        1,
    )[1]

    if language == "fa":

        await callback.answer(
            "🇮🇷 فارسی انتخاب شد."
        )

        await callback.message.edit_text(
            "🇮🇷 زبان ربات روی فارسی تنظیم شد."
        )

        return

    if language == "en":

        await callback.answer(
            "🇬🇧 English selected."
        )

        await callback.message.edit_text(
            "🇬🇧 Bot language changed to English."
        )


# ============================================================
# /ADVERTISEMENT
# ============================================================

@dp.message(
    F.text == "/Advertisement"
)
async def advertisement_handler(
    message: Message,
):

    await message.answer(
        "📢 <b>بخش تبلیغات</b>\n\n"
        "در این قسمت تبلیغات و اطلاعیه‌های مجاز "
        "نمایش داده خواهند شد.\n\n"
        "📭 در حال حاضر تبلیغی برای نمایش وجود ندارد.",
        parse_mode="HTML",
    )


# ============================================================
# /INFO
# ============================================================

@dp.message(
    F.text == "/info"
)
async def info_handler(
    message: Message,
):

    await message.answer(
        "ℹ️ <b>اطلاعات حقوقی</b>\n\n"
        "LiStEn_To_Mme یک ابزار پردازش و شناسایی "
        "محتوای صوتی و ویدیویی است.\n\n"
        "مسئولیت ارسال و استفاده از محتوای دارای "
        "حقوق مالکیت فکری بر عهده کاربر است.\n\n"
        "کاربران باید قوانین مربوط به حقوق مؤلفان، "
        "هنرمندان و پلتفرم‌های مربوطه را رعایت کنند.\n\n"
        "⚖️ استفاده از ربات به معنی انتقال یا واگذاری "
        "حقوق مالکیت فکری محتوا نیست.",
        parse_mode="HTML",
    )


# ============================================================
# DIRECT VIDEO - AUDIO EXTRACTION STATE
# ============================================================

@dp.message(
    AudioExtractionState.waiting_for_video,
    F.video,
)
async def direct_audio_extraction_handler(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    status_message = await message.answer(
        "🎧 ویدیو دریافت شد.\n"
        "⏳ در حال استخراج صدا..."
    )

    video_path = None
    audio_path = None

    try:

        video_path = await download_telegram_video(
            message
        )

        audio_path = await asyncio.to_thread(
            extract_audio,
            video_path,
        )

        audio = FSInputFile(
            audio_path
        )

        await message.answer_audio(
            audio=audio,
            caption=(
                "🎧 صدای ویدیو با موفقیت استخراج شد."
            ),
        )

        await status_message.delete()

    except Exception as error:

        print(
            "DIRECT AUDIO EXTRACTION ERROR:",
            repr(error),
        )

        await status_message.edit_text(
            "❌ استخراج صدا از ویدیو انجام نشد."
        )

    finally:

        if audio_path is not None:

            audio_path.unlink(
                missing_ok=True
            )

        if video_path is not None:

            video_path.unlink(
                missing_ok=True
            )


# ============================================================
# DIRECT VIDEO
# ============================================================

@dp.message(F.video)
async def direct_video_handler(
    message: Message,
):

    status_message = await message.answer(
        "🎬 ویدیو دریافت شد.\n"
        "⏳ در حال آماده‌سازی..."
    )

    video_path = None

    try:

        video_path = await download_telegram_video(
            message
        )

        print(
            "DIRECT VIDEO:",
            video_path,
        )

        video = FSInputFile(
            video_path
        )

        await message.answer_video(
            video=video,
            caption=(
                "✅ ویدیو دریافت شد.😊\n\n"
                "می‌تونی موسیقی ویدیو رو شناسایی کنی "
                "یا صدای آن را استخراج کنی."
            ),
            reply_markup=video_keyboard(
                video_path.name
            ),
        )

        await status_message.delete()

    except Exception as error:

        print(
            "DIRECT VIDEO ERROR:",
            repr(error),
        )

        await status_message.edit_text(
            "❌ پردازش ویدیو انجام نشد."
        )

        if video_path is not None:

            video_path.unlink(
                missing_ok=True
            )


# ============================================================
# LINK HANDLER
# ============================================================

@dp.message(
    F.text.regexp(URL_PATTERN)
)
async def link_handler(
    message: Message,
):

    url = extract_url(
        message.text
    )

    if not url:
        return

    platform = detect_platform(
        url
    )

    status_message = await message.answer(
        f"🔎 لینک شناسایی شد.\n"
        f"🌐 پلتفرم: {platform}\n\n"
        f"⏳ در حال دریافت محتوا..."
    )

    video_path = None

    try:

        video_path, title = await asyncio.to_thread(
            download_video,
            url,
        )

    except Exception as error:

        print(
            "DOWNLOAD ERROR:",
            repr(error),
        )

        await status_message.edit_text(
            "❌ نتونستم این لینک رو دانلود کنم."
        )

        return

    try:

        video = FSInputFile(
            video_path
        )

        await message.answer_video(
            video=video,
            caption=f"🎬 {title}",
            reply_markup=video_keyboard(
                video_path.name
            ),
        )

        await status_message.delete()

    except Exception as error:

        print(
            "TELEGRAM SEND ERROR:",
            repr(error),
        )

        await message.answer(
            "❌ ویدئو دانلود شد، ولی ارسال آن به تلگرام موفق نشد."
        )

        video_path.unlink(
            missing_ok=True
        )


# ============================================================
# MUSIC RECOGNITION
# ============================================================

@dp.callback_query(
    F.data.startswith("recognize_music:")
)
async def recognize_music_handler(
    callback: CallbackQuery,
):

    filename = callback.data.split(
        ":",
        1,
    )[1]

    video_path = (
        DOWNLOAD_DIR / filename
    )

    if not video_path.exists():

        await callback.answer(
            "❌ فایل ویدئو دیگر موجود نیست.",
            show_alert=True,
        )

        return

    await callback.answer(
        "🎵 در حال بررسی چند بخش از صدا..."
    )

    processing_message = (
        await callback.message.answer(
            "🎵 در حال شناسایی موسیقی...\n"
            "🔎 چند بخش مختلف صدا در حال بررسی است."
        )
    )

    audio_path = None
    sample_paths = []

    try:

        # ----------------------------------------------------
        # EXTRACT FULL AUDIO
        # ----------------------------------------------------

        audio_path = await asyncio.to_thread(
            extract_audio,
            video_path,
        )

        print(
            "EXTRACTED AUDIO:",
            audio_path,
        )

        # ----------------------------------------------------
        # CREATE AUDIO SAMPLES
        # ----------------------------------------------------

        sample_paths = await asyncio.to_thread(
            create_samples,
            audio_path,
        )

        print(
            "AUDIO SAMPLES:",
            sample_paths,
        )

        if not sample_paths:

            raise RuntimeError(
                "No audio samples were created."
            )

        # ----------------------------------------------------
        # RECOGNIZE MUSIC
        # ----------------------------------------------------

        result = await music_service.recognize(
            [
                str(path)
                for path in sample_paths
            ]
        )

        print(
            "FINAL MUSIC RESULT:",
            repr(result),
        )

        # ----------------------------------------------------
        # NO RESULT
        # ----------------------------------------------------

        if result is None:

            await processing_message.edit_text(
                "❌ نتونستم موسیقی این ویدیو رو شناسایی کنم.\n\n"
                "چند بخش مختلف صدا بررسی شد، اما "
                "نتیجه قابل اعتماد پیدا نشد."
            )

            return

        # ----------------------------------------------------
        # SEARCH MUSIC CATALOG
        # ----------------------------------------------------

        catalog_query_parts = []

        if result.title:

            catalog_query_parts.append(
                result.title
            )

        if result.artist:

            catalog_query_parts.append(
                result.artist
            )

        catalog_query = " ".join(
            catalog_query_parts
        ).strip()

        catalog_results = []

        if catalog_query:

            try:

                catalog_results = (
                    await catalog_service.search(
                        query=catalog_query,
                        limit=5,
                    )
                )

                print(
                    "CATALOG SEARCH QUERY:",
                    catalog_query,
                )

                print(
                    "CATALOG RESULTS:",
                    repr(catalog_results),
                )

            except Exception as error:

                print(
                    "CATALOG SEARCH ERROR:",
                    repr(error),
                )

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        if result.confidence is not None:

            confidence = (
                f"{max(0, min(100, float(result.confidence))):.0f}%"
            )

        else:

            confidence = "نامشخص"

        # ----------------------------------------------------
        # TRACK ID
        # ----------------------------------------------------

        track_id = (
            result.track_id
            or result.title
            or "unknown"
        )

        # ----------------------------------------------------
        # RESULT TEXT
        # ----------------------------------------------------

        text = (
            "🎵 <b>موسیقی شناسایی شد!</b>\n\n"
            f"🎼 <b>عنوان:</b> "
            f"{result.title}\n"
            f"👤 <b>هنرمند:</b> "
            f"{result.artist}\n"
        )

        if result.album:

            text += (
                f"💿 <b>آلبوم:</b> "
                f"{result.album}\n"
            )

        text += (
            f"🎯 <b>اطمینان:</b> "
            f"{confidence}"
        )

        # ----------------------------------------------------
        # BUILD MUSIC SEARCH URLS
        # ----------------------------------------------------

        search_query = (
            f"{result.title} {result.artist}"
        )

        encoded_query = quote_plus(
            search_query
        )

        google_url = (
            "https://www.google.com/search"
            f"?q={encoded_query}"
        )

        youtube_music_url = (
            "https://music.youtube.com/search"
            f"?q={encoded_query}"
        )

        spotify_url = (
            "https://open.spotify.com/search/"
            f"{encoded_query}"
        )

        # ----------------------------------------------------
        # SHOW RESULT
        # ----------------------------------------------------

        await processing_message.edit_text(
            text,
            reply_markup=music_result_keyboard(
                track_id=track_id,
                video_filename=video_path.name,
                google_url=google_url,
                youtube_music_url=youtube_music_url,
                spotify_url=spotify_url,
            ),
            parse_mode="HTML",
        )

    except Exception as error:

        print(
            "MUSIC RECOGNITION ERROR:",
            repr(error),
        )

        try:

            await processing_message.edit_text(
                "❌ هنگام شناسایی موسیقی خطایی رخ داد."
            )

        except Exception as edit_error:

            print(
                "PROCESSING MESSAGE EDIT ERROR:",
                repr(edit_error),
            )

    finally:

        # ----------------------------------------------------
        # DELETE SAMPLES
        # ----------------------------------------------------

        for sample_path in sample_paths:

            try:

                Path(sample_path).unlink(
                    missing_ok=True
                )

            except Exception as error:

                print(
                    "SAMPLE DELETE ERROR:",
                    repr(error),
                )

        # ----------------------------------------------------
        # DELETE EXTRACTED AUDIO
        # ----------------------------------------------------

        if audio_path is not None:

            try:

                audio_path.unlink(
                    missing_ok=True
                )

            except Exception as error:

                print(
                    "AUDIO DELETE ERROR:",
                    repr(error),
                )


# ============================================================
# AUDIO EXTRACTION FROM EXISTING VIDEO
# ============================================================

@dp.callback_query(
    F.data.startswith("audio:")
)
async def audio_handler(
    callback: CallbackQuery,
):

    filename = callback.data.split(
        ":",
        1,
    )[1]

    video_path = (
        DOWNLOAD_DIR / filename
    )

    if not video_path.exists():

        await callback.answer(
            "❌ فایل ویدئو دیگر موجود نیست.",
            show_alert=True,
        )

        return

    await callback.answer(
        "🎧 در حال استخراج صدا..."
    )

    processing_message = (
        await callback.message.answer(
            "🎧 در حال استخراج صدای ویدیو..."
        )
    )

    audio_path = None

    try:

        audio_path = await asyncio.to_thread(
            extract_audio,
            video_path,
        )

        audio = FSInputFile(
            audio_path
        )

        await callback.message.answer_audio(
            audio=audio,
            caption=(
                "🎧 صدای ویدیو با موفقیت استخراج شد."
            ),
        )

        await processing_message.delete()

    except Exception as error:

        print(
            "AUDIO ERROR:",
            repr(error),
        )

        await processing_message.edit_text(
            "❌ استخراج صدا از ویدیو انجام نشد."
        )

    finally:

        if audio_path is not None:

            audio_path.unlink(
                missing_ok=True
            )


# ============================================================
# MAIN
# ============================================================

async def main():

    validate_config()

    init_database()

    print(
        "STARTING => LiStEn_To_Mme_bot..."
    )

    me = await bot.get_me()

    print(
        f"BOT ONLINE: @{me.username}"
    )

    await dp.start_polling(
        bot
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )