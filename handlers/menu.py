from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 دانلود محتوا",
                    callback_data="menu_download",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎵 تشخیص موسیقی ویدیو",
                    callback_data="menu_music",
                ),
                InlineKeyboardButton(
                    text="🎧 استخراج صدای ویدیو",
                    callback_data="menu_audio",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✨ ابزارهای هوشمند",
                    callback_data="menu_ai",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 ساخت زیرنویس",
                    callback_data="menu_subtitles",
                ),
                InlineKeyboardButton(
                    text="📄 تبدیل ویدیو به متن",
                    callback_data="menu_transcribe",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎙️ دوبله",
                    callback_data="menu_dubbing",
                ),
                InlineKeyboardButton(
                    text="🌐 ترجمه",
                    callback_data="menu_translate",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 پرسش از ویدیو",
                    callback_data="menu_ask",
                ),
                InlineKeyboardButton(
                    text="🧠 خلاصه ویدیو",
                    callback_data="menu_summary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ تنظیمات",
                    callback_data="menu_settings",
                ),
            ],
        ]
    )


def music_result_keyboard(
    track_id: str,
    video_filename: str,
    google_url: str,
    youtube_music_url: str,
    spotify_url: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Google",
                    url=google_url,
                ),
                InlineKeyboardButton(
                    text="YouTube Music",
                    url=youtube_music_url,
                ),
                InlineKeyboardButton(
                    text="Spotify",
                    url=spotify_url,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔎 جستجو بر اساس هنرمند",
                    callback_data=f"search_artist:{track_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚠️ گزارش تشخیص اشتباه",
                    callback_data=f"report_music:{track_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎧 استخراج صدای ویدیو",
                    callback_data=f"extract_audio:{video_filename}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 بازگشت به منوی اصلی",
                    callback_data="back_to_main",
                ),
            ],
        ]
    )


def update_message_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 بازگشت به منوی اصلی",
                    callback_data="back_to_main",
                )
            ]
        ]
    )