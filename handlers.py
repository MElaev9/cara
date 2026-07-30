import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

ALLOWED_USERS = {470659949, 5934943041}


def is_allowed(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    return user_id in ALLOWED_USERS


async def access_denied(update: Update):
    text = "⛔ У вас нет доступа к этому боту."
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.answer(text, show_alert=True)


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
        "🫙 <b>Караван</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Расчёт продуктов для банкетов и мероприятий.\n\n"
        "Нажмите кнопку ниже, чтобы открыть приложение:"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🧾  Открыть Караван", web_app=WebAppInfo(url=miniapp_url))]]
    )
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
