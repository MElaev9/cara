import logging
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

ALLOWED_USERS = {470659949, 5934943041}

MENU_BUTTON_TEXT = "📋 Вызов панели"

# Кастомные (премиум) эмодзи можно вставить только в текст сообщения через
# HTML-тег <tg-emoji>, Telegram Bot API не поддерживает их в тексте кнопок.
PANEL_EMOJI_ID = "5983399041197675256"


def is_allowed(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    return user_id in ALLOWED_USERS


async def access_denied(update: Update):
    text = "⛔ У вас нет доступа к этому боту."
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.answer(text, show_alert=True)


def _bottom_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(MENU_BUTTON_TEXT)]],
        resize_keyboard=True,
        is_persistent=True,
    )


async def init_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет постоянную клавиатуру внизу экрана — вызывается только при /start."""
    if not is_allowed(update):
        await access_denied(update)
        return
    await update.message.reply_text("👇", reply_markup=_bottom_keyboard())
    await start(update, context)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await access_denied(update)
        return

    miniapp_url = os.environ.get("MINIAPP_URL")
    if not miniapp_url:
        await update.message.reply_text(
            "⚠️ Mini App не настроен. Обратитесь к администратору."
        )
        return

    text = (
        f'<tg-emoji emoji-id="{PANEL_EMOJI_ID}">📋</tg-emoji> <b>Караван</b>\n'
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Расчёт продуктов для банкетов и мероприятий.\n\n"
        "Нажмите кнопку ниже, чтобы открыть панель:"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть панель", web_app=WebAppInfo(url=miniapp_url))]]
    )
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
