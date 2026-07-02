import os
import json
import logging
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from calculator import DEPARTMENT_ORDER, format_amount

logger = logging.getLogger(__name__)

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1RTQix5kQRZeClKjC6ZDDQA0j6IlusJ_uJcFjAv34UPI")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
INDEX_SHEET_NAME = "📋 Все события"


def _get_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS environment variable is not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _get_or_create_index_sheet(service) -> int:
    """Получает или создаёт главный лист со списком событий."""
    sheet = service.spreadsheets()
    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = spreadsheet.get("sheets", [])

    for s in sheets:
        if s["properties"]["title"] == INDEX_SHEET_NAME:
            return s["properties"]["sheetId"]

    # Создаём главный лист
    resp = sheet.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"addSheet": {"properties": {
            "title": INDEX_SHEET_NAME,
            "index": 0,
        }}}]}
    ).execute()
    sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    # Заголовок главного листа
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{INDEX_SHEET_NAME}'!A1:D1",
        valueInputOption="RAW",
        body={"values": [["Мероприятие", "Гостей", "Дата", "Блюд"]]},
    ).execute()

    # Форматируем заголовок
    sheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                "textFormat": {"bold": True, "fontSize": 12,
                               "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER",
            }},
            "fields": "userEnteredFormat",
        }},
        {"autoResizeDimensions": {"dimensions": {
            "sheetId": sheet_id, "dimension": "COLUMNS",
            "startIndex": 0, "endIndex": 4,
        }}},
    ]}).execute()

    return sheet_id


def _add_to_index(service, event_name: str, guests: int, dish_count: int,
                  date_str: str, target_sheet_title: str):
    """Добавляет строку в главный лист со ссылкой на лист события."""
    sheet = service.spreadsheets()
    _get_or_create_index_sheet(service)

    # Получаем ID листа события для ссылки
    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    target_gid = None
    for s in spreadsheet.get("sheets", []):
        if s["properties"]["title"] == target_sheet_title:
            target_gid = s["properties"]["sheetId"]
            break

    # Ссылка на лист события
    sheet_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={target_gid}"

    # Находим первую пустую строку
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{INDEX_SHEET_NAME}'!A:A",
    ).execute()
    next_row = len(result.get("values", [])) + 1

    # Добавляем строку с формулой-ссылкой
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{INDEX_SHEET_NAME}'!A{next_row}:D{next_row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[
            f'=HYPERLINK("{sheet_url}","{event_name}")',
            guests,
            date_str,
            dish_count,
        ]]},
    ).execute()


def export_event_to_sheets(event_name: str, guests: int,
                           dish_names: list, ingredients: list) -> str:
    service = _get_service()
    sheet = service.spreadsheets()

    date_str = datetime.now().strftime("%d.%m.%Y")
    sheet_title = f"{event_name} {date_str}"[:100]

    # Создаём лист события
    resp = sheet.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"addSheet": {"properties": {"title": sheet_title}}}]}
    ).execute()
    sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    # ── Формируем данные ──────────────────────────────────────────────────
    rows = []

    # Шапка
    rows.append([f"🎉 {event_name}"])
    rows.append([f"👥 Гостей: {guests}"])
    rows.append([f"📅 Дата: {date_str}"])
    rows.append([])

    # Выбранные блюда
    rows.append(["🍽️ ВЫБРАННЫЕ БЛЮДА"])
    rows.append(["№", "Блюдо"])
    for i, name in enumerate(dish_names, 1):
        rows.append([i, name])
    rows.append([])

    # Закупка по отделам
    rows.append(["🛒 СПИСОК ЗАКУПКИ (+7% запас)"])
    rows.append(["Отдел", "Продукт", "Количество", "Ед. изм."])

    # Группируем по отделам
    from collections import defaultdict as dd
    by_dept = dd(list)
    for ing in ingredients:
        by_dept[ing["department"]].append(ing)

    for dept in DEPARTMENT_ORDER:
        items = by_dept.get(dept, [])
        if not items:
            continue
        first = True
        for ing in items:
            dept_label = dept if first else ""
            amount = ing["amount"]
            unit = ing["unit"]
            if unit == "шт":
                amount_str = str(int(amount))
            else:
                amount_str = f"{float(amount):.3f}".rstrip("0").rstrip(".")
            rows.append([dept_label, ing["name"], amount_str, unit])
            first = False
        rows.append(["", "", "", ""])  # пустая строка между отделами

    # ── Записываем данные ─────────────────────────────────────────────────
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_title}'!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    # ── Форматирование ────────────────────────────────────────────────────
    header_row = 4 + len(dish_names) + 2  # строка "🛒 СПИСОК ЗАКУПКИ"
    col_header_row = header_row + 1        # строка "Отдел | Продукт | ..."

    requests = [
        # Заголовок мероприятия — большой жирный
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True, "fontSize": 16},
                "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
            }},
            "fields": "userEnteredFormat",
        }},
        # Строки гостей и даты
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 3},
            "cell": {"userEnteredFormat": {
                "textFormat": {"fontSize": 11},
            }},
            "fields": "userEnteredFormat.textFormat",
        }},
        # Заголовок блюд
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 4, "endRowIndex": 5},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True, "fontSize": 12},
                "backgroundColor": {"red": 0.9, "green": 0.95, "blue": 1.0},
            }},
            "fields": "userEnteredFormat",
        }},
        # Шапка таблицы блюд
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 5, "endRowIndex": 6},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85},
            }},
            "fields": "userEnteredFormat",
        }},
        # Заголовок закупки
        {"repeatCell": {
            "range": {"sheetId": sheet_id,
                      "startRowIndex": header_row - 1, "endRowIndex": header_row},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True, "fontSize": 12},
                "backgroundColor": {"red": 0.9, "green": 1.0, "blue": 0.9},
            }},
            "fields": "userEnteredFormat",
        }},
        # Шапка таблицы закупки
        {"repeatCell": {
            "range": {"sheetId": sheet_id,
                      "startRowIndex": col_header_row - 1, "endRowIndex": col_header_row},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85},
            }},
            "fields": "userEnteredFormat",
        }},
        # Авторазмер всех колонок
        {"autoResizeDimensions": {"dimensions": {
            "sheetId": sheet_id, "dimension": "COLUMNS",
            "startIndex": 0, "endIndex": 4,
        }}},
        # Заморозить первую строку
        {"updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }},
    ]

    sheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": requests}).execute()

    # Добавляем в главный лист
    _add_to_index(service, event_name, guests, len(dish_names), date_str, sheet_title)

    return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={sheet_id}"


def delete_sheet_for_event(event_name: str):
    """Удаляет лист события и строку из главного листа."""
    service = _get_service()
    sheet = service.spreadsheets()

    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = spreadsheet.get("sheets", [])

    for s in sheets:
        title = s["properties"]["title"]
        if title.startswith(event_name):
            sheet_id = s["properties"]["sheetId"]
            sheet.batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
            ).execute()
            logger.info(f"Deleted sheet '{title}'")

            # Удаляем строку из главного листа
            _remove_from_index(service, event_name)
            break


def _remove_from_index(service, event_name: str):
    """Удаляет строку с мероприятием из главного листа."""
    sheet = service.spreadsheets()
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{INDEX_SHEET_NAME}'!A:A",
        ).execute()
        values = result.get("values", [])
        for i, row in enumerate(values):
            if row and event_name in str(row[0]):
                # Получаем sheetId главного листа
                spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
                index_id = None
                for s in spreadsheet.get("sheets", []):
                    if s["properties"]["title"] == INDEX_SHEET_NAME:
                        index_id = s["properties"]["sheetId"]
                        break
                if index_id is not None:
                    sheet.batchUpdate(
                        spreadsheetId=SPREADSHEET_ID,
                        body={"requests": [{"deleteDimension": {
                            "range": {
                                "sheetId": index_id,
                                "dimension": "ROWS",
                                "startIndex": i,
                                "endIndex": i + 1,
                            }
                        }}]},
                    ).execute()
                break
    except Exception as e:
        logger.warning(f"Could not remove from index: {e}")
