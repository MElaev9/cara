import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from database import init_db
from handlers import (
    start,
    add_event_start,
    receive_name,
    receive_guests,
    handle_dish_toggle,
    handle_category_info,
    save_dishes,
    handle_confirm,
    show_archive,
    show_event_card,
    export_to_sheets,
    delete_confirm,
    delete_do,
    cancel,
    WAITING_NAME,
    WAITING_GUESTS,
    CHOOSING_DISHES,
    CONFIRMING,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable is not set")

    init_db()

    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_event_start, pattern="^add_event$")],
        states={
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_GUESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_guests)],
            CHOOSING_DISHES: [
                CallbackQueryHandler(handle_dish_toggle, pattern="^dish_"),
                CallbackQueryHandler(save_dishes, pattern="^save_dishes$"),
                CallbackQueryHandler(handle_category_info, pattern="^cat_"),
            ],
            CONFIRMING: [
                CallbackQueryHandler(handle_confirm, pattern="^(confirm_save|cancel_event)$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(cancel, pattern="^cancel_event$"),
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(show_archive, pattern="^archive$"))
    app.add_handler(CallbackQueryHandler(show_event_card, pattern="^event_\\d+$"))
    app.add_handler(CallbackQueryHandler(export_to_sheets, pattern="^export_"))
    app.add_handler(CallbackQueryHandler(delete_confirm, pattern="^delete_confirm_"))
    app.add_handler(CallbackQueryHandler(delete_do, pattern="^delete_do_"))
    app.add_handler(CallbackQueryHandler(start, pattern="^main_menu$"))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
