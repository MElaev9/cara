import json
import logging
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import (
    get_all_dishes,
    get_dish_by_id,
    save_event,
    get_all_events,
    get_event_by_id,
)
from calculator import calculate_ingredients, format_amount
from sheets import export_event_to_sheets

logger = logging.getLogger(__name__)

# Conversation states
WAITING_NAME = 1
WAITING_GUESTS = 2
CHOOSING_DISHES = 3
CONFIRMING = 4

CATEGORY_ICONS = {
    "Салаты": "🥗",
    "Горячее": "🍖",
    "Гарниры": "🥔",
    "Закуски": "🧀",
    "Десерты": "🍰",
}

CATEGORY_DESCRIPTIONS = {
    "Салаты": "🥗 Салаты — расчёт идёт из нормы 1 порция на 3 гостей.",
    "Горячее": "🍖 Горячее — основное блюдо мероприятия, 1 порция на каждого гостя.",
    "Гарниры": "🥔 Гарниры — дополнение к горячему, 1 порция на каждого гостя.",
    "Закуски": "🧀 Закуски — лёгкие блюда к столу, 1 порция на 4 гостей.",
    "Десерты": "🍰 Десерты — сладкое к чаю, 1 порция на каждого гостя.",
}

EVENT_ICONS = ["🎉", "🎂", "🏢", "👶", "🎊", "🌟", "🥂", "🍽️"]

# Белый список — только эти пользователи могут использовать бота
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


def _main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить событие", callback_data="add_event")],
        [InlineKeyboardButton("📂 Архив событий", callback_data="archive")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await access_denied(update)
        return
    context.user_data.clear()
    text = "👋 Добро пожаловать в бот <b>«Караван»</b>!\n\nВыберите действие:"
    kb = _main_menu_keyboard()
    if update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


# ──────────────────────────────────────────────
# ADD EVENT FLOW
# ──────────────────────────────────────────────

async def add_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await access_denied(update)
        return ConversationHandler.END
    await update.callback_query.answer()
    context.user_data.clear()
    await update.callback_query.edit_message_text(
        "📝 <b>Новое мероприятие</b>\n\nВведите название мероприятия:",
        parse_mode="HTML",
    )
    return WAITING_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❗ Название не может быть пустым. Введите снова:")
        return WAITING_NAME
    context.user_data["event_name"] = name
    await update.message.reply_text(
        f"✅ Название: <b>{name}</b>\n\nВведите количество гостей (целое число):",
        parse_mode="HTML",
    )
    return WAITING_GUESTS


async def receive_guests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❗ Введите положительное целое число. Например: 120")
        return WAITING_GUESTS
    context.user_data["guests"] = int(text)
    context.user_data["selected_dishes"] = []
    await _send_dish_catalog(update.message, context)
    return CHOOSING_DISHES


async def _send_dish_catalog(target, context: ContextTypes.DEFAULT_TYPE, edit=False):
    dishes = get_all_dishes()
    selected = set(context.user_data.get("selected_dishes", []))

    # Group by category
    categories = defaultdict(list)
    for d in dishes:
        categories[d["category"]].append(d)

    keyboard = []
    for category in ["Салаты", "Горячее", "Гарниры", "Закуски", "Десерты"]:
        if category not in categories:
            continue
        icon = CATEGORY_ICONS.get(category, "🍴")
        keyboard.append([InlineKeyboardButton(f"── {icon} {category} ──", callback_data=f"cat_{category}")])
        row = []
        for dish in categories[category]:
            is_selected = dish["id"] in selected
            label = f"✅ {dish['name']}" if is_selected else dish["name"]
            row.append(InlineKeyboardButton(label, callback_data=f"dish_{dish['id']}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

    keyboard.append([InlineKeyboardButton("✅ Сохранить выбор", callback_data="save_dishes")])

    count = len(selected)
    text = (
        f"🍽️ <b>Выберите блюда</b>\n\n"
        f"Выбрано блюд: <b>{count}</b>\n\n"
        f"Нажмите на блюдо для выбора/отмены.\n"
        f"После окончания нажмите «Сохранить выбор»."
    )
    kb = InlineKeyboardMarkup(keyboard)

    if edit:
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def handle_category_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    category = query.data.replace("cat_", "", 1)
    description = CATEGORY_DESCRIPTIONS.get(category, category)
    await query.answer(text=description, show_alert=True)


async def handle_dish_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    dish_id = int(query.data.split("_")[1])
    selected = context.user_data.get("selected_dishes", [])

    if dish_id in selected:
        selected.remove(dish_id)
    else:
        selected.append(dish_id)

    context.user_data["selected_dishes"] = selected
    await _send_dish_catalog(query, context, edit=True)
    return CHOOSING_DISHES


async def save_dishes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected = context.user_data.get("selected_dishes", [])
    if not selected:
        await query.answer("⚠️ Выберите хотя бы одно блюдо!", show_alert=True)
        return CHOOSING_DISHES

    await _show_confirmation(query, context, edit=True)
    return CONFIRMING


async def _show_confirmation(target, context, edit=False):
    name = context.user_data["event_name"]
    guests = context.user_data["guests"]
    selected_ids = context.user_data["selected_dishes"]

    dish_names = []
    for did in selected_ids:
        d = get_dish_by_id(did)
        if d:
            dish_names.append(d["name"])

    dishes_text = "\n".join(f"• {n}" for n in dish_names)
    text = (
        f"📋 <b>Проверьте данные мероприятия</b>\n\n"
        f"<b>Название</b>\n{name}\n\n"
        f"<b>Количество гостей</b>\n{guests}\n\n"
        f"<b>Выбранные блюда</b>\n{dishes_text}"
    )
    keyboard = [
        [
            InlineKeyboardButton("✅ Сохранить событие", callback_data="confirm_save"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_event"),
        ]
    ]
    kb = InlineKeyboardMarkup(keyboard)
    if edit:
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def confirm_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_confirmation(update.message, context)
    return CONFIRMING


async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_event":
        context.user_data.clear()
        await query.edit_message_text(
            "❌ Создание события отменено.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
            ),
        )
        return ConversationHandler.END

    # Save
    name = context.user_data["event_name"]
    guests = context.user_data["guests"]
    dish_ids = context.user_data["selected_dishes"]
    save_event(name, guests, dish_ids)
    context.user_data.clear()

    await query.edit_message_text(
        f"🎉 Событие <b>«{name}»</b> успешно сохранено!\n\nТеперь оно доступно в архиве.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
        ),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Отменено.")
    return ConversationHandler.END


# ──────────────────────────────────────────────
# ARCHIVE
# ──────────────────────────────────────────────

async def show_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await access_denied(update)
        return
    query = update.callback_query
    await query.answer()

    events = get_all_events()
    if not events:
        await query.edit_message_text(
            "📂 <b>Архив пуст</b>\n\nСоздайте первое мероприятие!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
            ),
        )
        return

    keyboard = []
    for i, ev in enumerate(events):
        icon = EVENT_ICONS[i % len(EVENT_ICONS)]
        keyboard.append(
            [InlineKeyboardButton(f"{icon} {ev['name']} ({ev['guests']} гостей)", callback_data=f"event_{ev['id']}")]
        )
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])

    await query.edit_message_text(
        f"📂 <b>Архив мероприятий</b>\n\nВсего: {len(events)}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ──────────────────────────────────────────────
# EVENT CARD
# ──────────────────────────────────────────────

async def show_event_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    event_id = int(query.data.split("_")[1])
    event = get_event_by_id(event_id)
    if not event:
        await query.edit_message_text("⚠️ Мероприятие не найдено.")
        return

    dish_ids = json.loads(event["dish_ids"])
    dish_names = []
    for did in dish_ids:
        d = get_dish_by_id(did)
        if d:
            dish_names.append(d["name"])

    # Calculate ingredients
    ingredients = calculate_ingredients(event["guests"], dish_ids)

    dishes_text = "\n".join(f"• {n}" for n in dish_names)
    ing_lines = "\n".join(
        f"• {ing['name']} — {format_amount(ing['amount'], ing['unit'])}"
        for ing in ingredients
    )

    # Split into two messages if too long
    header = (
        f"🎉 <b>{event['name']}</b>\n\n"
        f"<b>Количество гостей:</b> {event['guests']}\n\n"
        f"<b>Выбранные блюда:</b>\n{dishes_text}\n\n"
        f"<b>🛒 Необходимые продукты (с запасом +7%):</b>\n{ing_lines}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Экспорт в Google Таблицу", callback_data=f"export_{event_id}")],
        [InlineKeyboardButton("◀️ Назад к архиву", callback_data="archive")],
    ])

    # Telegram message limit is 4096 chars; split if needed
    if len(header) <= 4096:
        await query.edit_message_text(header, parse_mode="HTML", reply_markup=kb)
    else:
        part1 = (
            f"🎉 <b>{event['name']}</b>\n\n"
            f"<b>Количество гостей:</b> {event['guests']}\n\n"
            f"<b>Выбранные блюда:</b>\n{dishes_text}"
        )
        await query.edit_message_text(part1, parse_mode="HTML")
        part2 = f"<b>🛒 Необходимые продукты (с запасом +7%):</b>\n{ing_lines}"
        await query.message.reply_text(part2, parse_mode="HTML", reply_markup=kb)


# ──────────────────────────────────────────────
# EXPORT TO GOOGLE SHEETS
# ──────────────────────────────────────────────

async def export_to_sheets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    event_id = int(query.data.split("_")[1])
    event = get_event_by_id(event_id)
    if not event:
        await query.answer("⚠️ Мероприятие не найдено.", show_alert=True)
        return

    await query.message.reply_text("⏳ Экспортирую в Google Таблицу...")

    dish_ids = json.loads(event["dish_ids"])
    dish_names = []
    for did in dish_ids:
        d = get_dish_by_id(did)
        if d:
            dish_names.append(d["name"])

    ingredients = calculate_ingredients(event["guests"], dish_ids)

    try:
        url = export_event_to_sheets(
            event_name=event["name"],
            guests=event["guests"],
            dish_names=dish_names,
            ingredients=ingredients,
        )
        await query.message.reply_text(
            f"✅ Готово! Данные экспортированы.\n\n📊 <a href='{url}'>Открыть таблицу</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Sheets export error: {e}")
        await query.message.reply_text(
            "❌ Ошибка при экспорте. Проверьте настройки Google API."
        )
