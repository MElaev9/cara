import os
import logging
from flask import Flask, request, abort

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения Render!")

PORT = int(os.environ.get("PORT", 10000))

# Render даёт домен в переменной RENDER_EXTERNAL_HOSTNAME
# Если её нет — fallback на localhost (для теста)
HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "localhost")
WEBHOOK_PATH = f"/telegram-webhook"  # можно сделать длиннее/секретнее
WEBHOOK_URL = f"https://{HOSTNAME}{WEBHOOK_PATH}"

app = Flask(__name__)

# Глобальное приложение python-telegram-bot
application: Application = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Суп", callback_data="Суп")],
        [InlineKeyboardButton("Пицца", callback_data="Пицца")],
        [InlineKeyboardButton("Салат", callback_data="Салат")],
        [InlineKeyboardButton("Десерт", callback_data="Десерт")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Добро пожаловать в Караван! Выберите блюдо:", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(f"Вы выбрали: {query.data}\n\nСкоро приготовим! 🍲")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Напишите /start чтобы увидеть меню.")


def init_application():
    global application
    if application is not None:
        return

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


@app.route("/", methods=["GET"])
def health_check():
    return "Telegram бот на webhook работает"


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_data = request.get_json(silent=True)
        if json_data is None:
            abort(400)

        update = Update.de_json(json_data, application.bot)
        if update:
            # Кладём обновление в очередь (не блокируем поток)
            application.update_queue.put_nowait(update)
        return "OK", 200

    abort(403)


def set_webhook_once():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            application.bot.set_webhook(
                url=WEBHOOK_URL,
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
        )
        logger.info(f"Webhook успешно установлен: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Ошибка при установке webhook: {e}")
        raise
    finally:
        loop.close()


if __name__ == "__main__":
    # Локальный запуск (python bot.py) — для теста
    init_application()
    set_webhook_once()  # только для локального теста с ngrok
    app.run(host="0.0.0.0", port=PORT, debug=True)
else:
    # На Render (gunicorn запускает приложение)
    init_application()
    # set_webhook_once() НЕ вызываем здесь — делаем это один раз вручную после деплоя