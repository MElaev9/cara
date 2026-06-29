import json
from collections import defaultdict
from database import get_dish_by_id, get_ingredients_for_dish

RESERVE = 1.07  # 7% запас

UNIT_DISPLAY_ORDER = ["г", "кг", "мл", "л", "шт"]

# Коэффициенты категорий уже учтены через поле `serves` в рецепте,
# но для удобства храним нормативы (не используются в расчёте напрямую)
CATEGORY_SERVES = {
    "Салаты": 3,
    "Закуски": 4,
    "Горячее": 1,
    "Гарниры": 1,
    "Десерты": 1,
    "Напитки": 1,
}


def calculate_ingredients(guests: int, dish_ids: list[int]) -> list[dict]:
    """
    Рассчитывает суммарный список ингредиентов для мероприятия.
    Возвращает список словарей: {name, amount, unit}
    Количество уже умножено на коэффициент гостей и запас 7%.
    Одинаковые ингредиенты объединены.
    """
    totals: dict[tuple, float] = defaultdict(float)  # (name_lower, unit) -> amount

    for dish_id in dish_ids:
        dish = get_dish_by_id(dish_id)
        if dish is None:
            continue

        serves = dish["serves"]
        # Сколько раз нужно приготовить рецепт
        multiplier = guests / serves

        ingredients = get_ingredients_for_dish(dish_id)
        for ing in ingredients:
            key = (ing["name"].strip().lower(), ing["unit"])
            totals[key] += ing["amount"] * multiplier

    # Применяем 7% запас и нормализуем единицы
    result = []
    seen_names: dict[str, tuple] = {}

    for (name_lower, unit), amount in totals.items():
        amount_with_reserve = amount * RESERVE
        # Нормализация: г -> кг, мл -> л (если >=1000)
        display_amount, display_unit = normalize_unit(amount_with_reserve, unit)

        # Группировка по нормализованному имени (может быть г и кг одного ингредиента)
        # Используем name_lower как ключ для поиска оригинального названия
        result.append({
            "name": _capitalize(name_lower),
            "amount": display_amount,
            "unit": display_unit,
        })

    # Финальная сортировка по имени
    result.sort(key=lambda x: x["name"])
    return result


def normalize_unit(amount: float, unit: str) -> tuple[float, str]:
    """Переводит г в кг и мл в л, если сумма ≥1000."""
    if unit == "г" and amount >= 1000:
        return round(amount / 1000, 2), "кг"
    if unit == "мл" and amount >= 1000:
        return round(amount / 1000, 2), "л"
    if unit in ("кг", "л"):
        return round(amount, 2), unit
    if unit == "шт":
        return round(amount), "шт"
    return round(amount, 2), unit


def _capitalize(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


def format_amount(amount, unit) -> str:
    if unit == "шт":
        return f"{int(amount)} шт"
    return f"{amount} {unit}"
