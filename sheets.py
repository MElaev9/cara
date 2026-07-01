import os
import json
import logging
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1RTQix5kQRZeClKjC6ZDDQA0j6IlusJ_uJcFjAv34UPI")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS environment variable is not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def export_event_to_sheets(event_name: str, guests: int, dish_names: list, ingredients: list) -> str:
    """
    Создаёт новый лист в таблице для мероприятия и заполняет его данными.
    Возвращает ссылку на таблицу.
    """
    service = _get_service()
    sheet = service.spreadsheets()

    # Название листа — название мероприятия + дата
    date_str = datetime.now().strftime("%d.%m.%Y")
    sheet_title = f"{event_name} ({date_str})"[:100]  # Ограничение Google

    # Создаём новый лист
    body = {
        "requests": [{
            "addSheet": {
                "properties": {
                    "title": sheet_title,
                }
            }
        }]
    }
    response = sheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()
    sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]

    # Формируем данные для записи
    rows = []

    # Заголовок
    rows.append([f"🎉 {event_name}"])
    rows.append([f"Количество гостей: {guests}"])
    rows.append([])

    # Блюда
    rows.append(["ВЫБРАННЫЕ БЛЮДА"])
    for name in dish_names:
        rows.append([f"• {name}"])
    rows.append([])

    # Продукты
    rows.append(["СПИСОК ЗАКУПКИ (с запасом +7%)"])
    rows.append(["Продукт", "Количество", "Единица"])
    for ing in ingredients:
        from calculator import format_amount
        amount = ing["amount"]
        unit = ing["unit"]
        if unit == "шт":
            amount_str = str(int(amount))
        else:
            amount_str = str(amount).replace(".", ",")
        rows.append([ing["name"], amount_str, unit])

    # Записываем данные
    range_name = f"'{sheet_title}'!A1"
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    # Форматирование: жирный заголовок и шапку таблицы
    requests = [
        # Жирный заголовок (строка 1)
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True, "fontSize": 14}
                    }
                },
                "fields": "userEnteredFormat.textFormat",
            }
        },
        # Жирный заголовок блюд
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 3,
                    "endRowIndex": 4,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True}
                    }
                },
                "fields": "userEnteredFormat.textFormat",
            }
        },
        # Жирный заголовок закупки
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 4 + len(dish_names) + 1,
                    "endRowIndex": 4 + len(dish_names) + 3,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True}
                    }
                },
                "fields": "userEnteredFormat.textFormat",
            }
        },
        # Авторазмер колонки A
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 3,
                }
            }
        },
    ]

    sheet.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests}
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"


def delete_sheet_for_event(event_name: str):
    """Удаляет лист с данным мероприятием из таблицы."""
    service = _get_service()
    sheet = service.spreadsheets()

    # Получаем список всех листов
    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = spreadsheet.get("sheets", [])

    # Ищем листы, название которых начинается с имени события
    for s in sheets:
        title = s["properties"]["title"]
        if title.startswith(event_name):
            sheet_id = s["properties"]["sheetId"]
            sheet.batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
            ).execute()
            logger.info(f"Deleted sheet '{title}'")
