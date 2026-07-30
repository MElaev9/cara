# Бот «Караван» — launcher для Mini App

## Описание

Тонкий Telegram-бот без собственной логики. Единственная задача — по команде `/start`
показать разрешённым пользователям кнопку для открытия Mini App «Караван».

Вся функциональность (создание мероприятий, каталог блюд, архив, расчёт закупок,
экспорт в Google Таблицы) реализована в Mini App и его backend:

- `karavan-miniapp` — фронтенд Mini App
- `karavan-api` — backend (FastAPI), хранит данные и считает закупки

---

## Структура проекта

```
karavan/
├── bot.py           # Точка входа, регистрация /start
├── handlers.py      # Проверка доступа + отправка кнопки Mini App
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Запуск

### Локально (без Docker)

```bash
pip install -r requirements.txt
export BOT_TOKEN=ваш_токен_от_BotFather
export MINIAPP_URL=https://ваш-mini-app-домен
python bot.py
```

### Через Docker Compose

```bash
echo "BOT_TOKEN=ваш_токен_от_BotFather" > .env
echo "MINIAPP_URL=https://ваш-mini-app-домен" >> .env
docker-compose up -d
```

### Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) |
| `MINIAPP_URL` | URL задеплоенного `karavan-miniapp` |
