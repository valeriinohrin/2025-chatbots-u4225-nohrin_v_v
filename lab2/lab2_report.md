# Lab 2 — Подключение бота к данным (CSV)  

**University:** ITMO University  
**Faculty:** FICT  
**Course:** Vibe Coding: AI-боты для бизнеса  
**Year:** 2025/2026  
**Group:** U4225  
**Author:** Нохрин Валерий Витальевич  
**Lab:** Lab2  
**Date of create:** 2025-10-28  
**Date of finished:** 

---

## 1. Коротко о решении
Бот Telegram (python-telegram-bot 21.x) подключён к файловому хранилищу CSV и умеет:
- принимать заявки от клиента (ФИО, email, пол, согласие на ОПП, выдача ссылки на курс);
- записывать заявки в `lab2/data/leads.csv`;
- показывать админские команды: `/inbox`, `/find <текст>`, `/set_status <id> <new|in_work|done|rejected>`;
- выгружать заявки в CSV-файл, который корректно открывается в Excel — команда `/export_csv`.

Интеграция соответствует варианту *«Работа с файлами (CSV/Excel)»* из методички по ЛР2. :contentReference[oaicite:0]{index=0}

---

## 2. Источник и структура данных
**Источник:** локальные CSV в папке `lab2/data/`.

**Файл:** `lab2/data/leads.csv`  
**Колонки (порядок):**
1. `id` — автоинкремент (int)  
2. `user_name` — имя в TG (str)  
3. `fio` — ФИО (str)  
4. `email` — Email (str)  
5. `topic` — тема (str)  
6. `status` — `new|in_work|done|rejected` (str)  
7. `details` — произвольный текст (str)  
8. `created_at` — ISO-дата/время (str)

Экспорт создаётся как `lab2/data/export/leads_YYYY-MM-DD_HHMMSS.csv` и открывается в Excel по столбцам (разделитель `,`, кодировка UTF-8-BOM).

---

## 3. Команды бота
**Клиент:**
- `/start` — воронка: согласие на ОПП → ФИО → email → пол → выдача `COURSE_URL`, запись в `leads.csv`.

**Админ (по `ADMIN_TELEGRAM_ID`):**
- `/inbox` — последние 10 заявок (id, ФИО, email, статус, дата).
- `/find <текст>` — поиск по ФИО/email/теме/деталям.
- `/set_status <id> <new|in_work|done|rejected>` — смена статуса.
- `/export_csv` — выгрузка в CSV и отправка файла.

---

## 4. Архитектура и файлы
repo-root/
.env
lab1/
bot/main.py # код бота (ЛР1+ЛР2)
lab2/
data/
leads.csv # база заявок
export/ # папка для выгрузок
files_io.py # работа с CSV: add_lead/list_leads/find_leads/set_status/export_csv
init.py
lab2_report.md # этот отчёт
README.md

---

## 5. Ключевые фрагменты (ссылочно)
- **Чтение/запись CSV** (`lab2/files_io.py`): функции `add_lead`, `list_leads`, `find_leads`, `set_status`, `export_csv` (разделитель `,`, `encoding="utf-8-sig"` для Excel).
- **Админ-команды** (`lab1/bot/main.py`): хэндлеры `/inbox`, `/find`, `/set_status`, `/export_csv`.
- **Защита админки:** проверка `is_admin(update.effective_user.id)` против `ADMIN_TELEGRAM_ID` из `.env`.
- **Клиентская воронка:** согласие на ОПП → сбор ФИО/email/пола → запись → выдача `COURSE_URL`.

---

## 6. Тестирование
1. Запуск в терминале:

   ```bash
   cd ~/<путь-к-репо>
   source .venv/bin/activate
   python lab1/bot/main.py

2 Клиентский сценарий: /start, ввожу данные, получаю ссылку, в leads.csv появилась строка.

3. Админ-сценарии (с аккаунта с ADMIN_TELEGRAM_ID):

/inbox показывает последние заявки.
/find Иван находит тестовую заявку.
/set_status 5 in_work меняет статус.
/export_csv присылает csv, файл открывается в Excel, колонки разнесены корректно.

4 Обработки ошибок:

неверный формат у /set_status = подсказка по формату;
пустая выборка у /find и /inbox = вежливое сообщение;
проверки на доступ к админским командам.

## 7. Видео-демо

Доступно по ссылке: 

## 8. Промпт-инжиниринг

Работал по методичке ЛР2: «Выбрать тип интеграции, составить промпт, сгенерировать код, протестировать, улучшить». 

## 9. Выводы

Бот подключён к файловому источнику данных (CSV), отвечает требованиям ЛР2.
Экспорт теперь стабильно открывается в Excel.
