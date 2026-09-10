from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
)

from database import add_music_report

from handlers.menu import (
    main_menu,
    update_message_keyboard,
)

from handlers.states import AudioExtractionState


router = Router()


# ============================================================
# REPORT WRONG MUSIC
# ============================================================

@router.callback_query(
    F.data.startswith("report_music:")
)
async def report_music_handler(
    callback: CallbackQuery,
):
    track_id = callback.data.split(
        ":",
        1,
    )[1]

    print(
        "WRONG MUSIC REPORT:",
        track_id,
    )

    await callback.answer(
        "✅ گزارش شما ثبت شد. ممنون که اطلاع دادی.",
        show_alert=True,
    )
    # --------------------------------------------------------
    # SAVE REPORT
    # --------------------------------------------------------

    try:
        report_id = add_music_report(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            track_id=track_id,
        )

        print(
            "MUSIC REPORT SAVED:",
            report_id,
            track_id,
        )

    except Exception as error:
        print(
            "MUSIC REPORT ERROR:",
            repr(error),
        )

        await callback.answer(
            "❌ ثبت گزارش انجام نشد.",
            show_alert=True,
        )
        return

    # --------------------------------------------------------
    # REPORT SUCCESS
    # --------------------------------------------------------

    await callback.answer(
        "✅ گزارش شما ثبت شد. ممنون که اطلاع دادی.",
        show_alert=True,
    )

    # --------------------------------------------------------
    # REMOVE ONLY REPORT BUTTON
    # --------------------------------------------------------

    try:
        current_markup = callback.message.reply_markup

        if not current_markup:
            return

        new_keyboard = []

        for row in current_markup.inline_keyboard:

            new_row = []

            for button in row:

                # فقط دکمه گزارش حذف شود
                if (
                    button.callback_data
                    and button.callback_data.startswith(
                        "report_music:"
                    )
                ):
                    continue

                new_row.append(button)

            if new_row:
                new_keyboard.append(new_row)

        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=new_keyboard
            )
        )

        print("REPORT BUTTON REMOVED")

    except Exception as error:
        print(
            "MUSIC REPORT KEYBOARD UPDATE ERROR:",
            repr(error),
        )


# ============================================================
# BACK TO MAIN
# ============================================================

@router.callback_query(
    F.data == "back_to_main"
)
async def back_to_main_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()

    await callback.answer()

    await callback.message.edit_text(
        "سلام 👋\n\n"
        "به *LiStEn_To_Mme* خوش اومدی.\n\n"
        "لینک ویدیو، عکس یا محتوای موردنظرت رو بفرست "
        "یا از منوی زیر استفاده کن.",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# MENU CALLBACKS
# ============================================================

@router.callback_query(
    F.data.startswith("menu_")
)
async def menu_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    messages = {
        "menu_download": (
            "📥 دانلود محتوا در حال بروزرسانی است."
        ),

        "menu_music": (
            "🎵 ویدیویی که می‌خواهی موسیقی آن "
            "شناسایی شود را بفرست."
        ),

        "menu_audio": (
            "🎧 ویدیویی که می‌خواهی صدای آن "
            "استخراج شود را بفرست."
        ),

        "menu_ai": (
            "✨ ابزارهای هوشمند در حال بروزرسانی هستند."
        ),

        "menu_transcribe": (
            "📝 تبدیل ویدیو به متن در حال بروزرسانی است."
        ),

        "menu_subtitles": (
            "📄 ساخت زیرنویس در حال بروزرسانی است."
        ),

        "menu_translate": (
            "🌐 ترجمه در حال بروزرسانی است."
        ),

        "menu_dubbing": (
            "🎙️ دوبله در حال بروزرسانی است."
        ),

        "menu_summary": (
            "🧠 خلاصه ویدیو در حال بروزرسانی است."
        ),

        "menu_ask": (
            "💬 پرسش از ویدیو در حال بروزرسانی است."
        ),

        "menu_settings": (
            "⚙️ تنظیمات در حال بروزرسانی است."
        ),
    }

    if callback.data == "menu_music":

        await state.clear()

    elif callback.data == "menu_audio":

        await state.set_state(
            AudioExtractionState.waiting_for_video
        )

    else:

        await state.clear()

    text = messages.get(
        callback.data,
        "🛠️ این قابلیت در حال بروزرسانی است.",
    )

    await callback.answer()

    await callback.message.edit_text(
        text,
        reply_markup=update_message_keyboard(),
    )