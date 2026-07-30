import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from handlers import start, init_keyboard, MENU_BUTTON_TEXT

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable is not set")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", init_keyboard))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{MENU_BUTTON_TEXT}$"), start))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
