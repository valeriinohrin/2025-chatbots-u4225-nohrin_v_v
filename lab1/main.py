# -*- coding: utf-8 -*-
"""
lab1/main.py — бот ЛР1/ЛР2.
Фиксы:
- /start: стабильный запуск сценария
- экспорт: работают /export_csv и /export (алиас), меню обновляется
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from telegram import (
    Update, BotCommand, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputFile
)
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# ── ЛОГИ ───────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("bot")

# ── ПУТИ / ИМПОРТ lab2 ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lab2.files_io import (   # type: ignore
    add_lead, list_leads, find_leads, set_status, export_csv, ALLOWED_STATUSES
)

# ── ENV ───────────────────────────────────────────────────────────────────────
ENV = ROOT / ".env"
ENV_VARS: Dict[str, str] = {}
if ENV.exists():
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        ENV_VARS[k.strip()] = v.strip()

BOT_TOKEN = ENV_VARS.get("BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = ENV_VARS.get("ADMIN_TELEGRAM_ID", "")
COURSE_URL = ENV_VARS.get("COURSE_URL", "https://xn--80ablbmpklx3m.xn--p1ai")
DATA_DIR   = ENV_VARS.get("DATA_DIR", "lab2/data")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден в .env")

log.info(f"BOT_TOKEN = {BOT_TOKEN[:8]}...{BOT_TOKEN[-4:]} (len={len(BOT_TOKEN)})")
log.info(f"ADMIN_TELEGRAM_ID = {ADMIN_TELEGRAM_ID}")
log.info(f"COURSE_URL = {COURSE_URL}")
log.info(f"DATA_DIR = {DATA_DIR}")

def is_admin(update: Update) -> bool:
    try:
        return str(update.effective_user.id) == str(ADMIN_TELEGRAM_ID)
    except Exception:
        return False

def safe_add_lead(fio: str, email: str, gender: str) -> int:
    """Аккуратно зовём add_lead при разных сигнатурах; возвращаем id либо 0."""
    try:
        return int(add_lead(fio, email, gender))  # type: ignore
    except TypeError:
        pass
    try:
        return int(add_lead(0, "user", fio, email, "Курс", gender))  # type: ignore
    except TypeError:
        pass
    add_lead(fio, email, gender)  # type: ignore
    return 0

# ── КЛИЕНТСКИЙ СЦЕНАРИЙ ───────────────────────────────────────────────────────
ASK_CONSENT, ASK_FIO, ASK_EMAIL, ASK_GENDER = range(4)

CONSENT_KB = ReplyKeyboardMarkup([["Согласен"], ["Не согласен"]], resize_keyboard=True)
GENDER_KB  = ReplyKeyboardMarkup([["Мальчик", "Девочка"], ["Пока не знаю"]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт всегда отвечает (даже если разговор уже был)."""
    # Сбросим незавершённый разговор, если был
    context.user_data.clear()
    await update.message.reply_text(
        "Подтверди согласие на обработку персональных данных.",
        reply_markup=CONSENT_KB,
    )
    return ASK_CONSENT

async def consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()
    if text.startswith("не"):
        await update.message.reply_text(
            "Ок, без согласия не можем продолжать. /start — начать заново.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END
    await update.message.reply_text("Напиши ФИО полностью:", reply_markup=ReplyKeyboardRemove())
    return ASK_FIO

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fio"] = (update.message.text or "").strip()
    await update.message.reply_text("Укажи e-mail:")
    return ASK_EMAIL

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["email"] = (update.message.text or "").strip()
    await update.message.reply_text("Кто у вас ожидается? Выбери:", reply_markup=GENDER_KB)
    return ASK_GENDER

async def finish_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fio    = str(context.user_data.get("fio", "")).strip()
    email  = str(context.user_data.get("email", "")).strip()
    gender = (update.message.text or "").strip()
    lead_id = safe_add_lead(fio, email, gender)
    suffix  = f" №{lead_id}" if lead_id else ""
    await update.message.reply_text(
        f"✅ Заявка{suffix} сохранена.\nСсылка на курс: {COURSE_URL}",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Ок, прервали. /start — начать заново.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ── АДМИН ─────────────────────────────────────────────────────────────────────
def _row_to_line(r: Any) -> str:
    if isinstance(r, dict):
        return f"#{r.get('id')} | {r.get('fio')} | {r.get('email')} | {r.get('gender')} | {r.get('status')}"
    try:
        return " | ".join(map(str, r))
    except Exception:
        return str(r)

async def inbox_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Команда недоступна.")
        return
    rows = list_leads(limit=10)
    if not rows:
        await update.message.reply_text("Заявок пока нет.")
        return
    await update.message.reply_text("\n".join(_row_to_line(r) for r in rows))

async def find_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Команда недоступна.")
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Использование: /find Иван")
        return
    rows = find_leads(query=query, limit=10)
    if not rows:
        await update.message.reply_text("Ничего не найдено.")
        return
    await update.message.reply_text("\n".join(_row_to_line(r) for r in rows))

async def set_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Команда недоступна.")
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"Формат: /set_status <id> <{'|'.join(ALLOWED_STATUSES)}>")
        return
    lead_id = context.args[0]
    new_status = context.args[1]
    ok, msg = set_status(lead_id, new_status)
    await update.message.reply_text(msg)

async def export_csv_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основная команда экспорта."""
    if not is_admin(update):
        await update.message.reply_text("Команда недоступна.")
        return
    path = export_csv()
    if not path or not os.path.exists(path):
        await update.message.reply_text("Экспорт не получился.")
        return
    await update.message.reply_document(InputFile(path), caption=os.path.basename(path))

async def export_alias_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Алиас для старой кнопки /export → вызывает /export_csv."""
    await export_csv_cmd(update, context)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start — оформить доступ к курсу\n"
        "/inbox — последние заявки (админ)\n"
        "/find — поиск заявок (админ)\n"
        "/set_status — сменить статус (админ)\n"
        "/export_csv — выгрузка заявок (CSV, админ)\n"
        "/export — то же, что /export_csv\n"
    )

# ── КОМАНДЫ В МЕНЮ ────────────────────────────────────────────────────────────
async def post_init_set_commands(app: Application) -> None:
    cmds = [
        BotCommand("start", "оформить доступ к курсу"),
        BotCommand("inbox", "последние заявки (админ)"),
        BotCommand("find", "поиск заявок (админ)"),
        BotCommand("set_status", "сменить статус (админ)"),
        BotCommand("export_csv", "выгрузка заявок (CSV, админ)"),
        BotCommand("export", "выгрузка заявок (CSV, админ)"),  # ← алиас
        BotCommand("help", "помощь"),
    ]
    await app.bot.set_my_commands(cmds)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def build_app() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init_set_commands).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_CONSENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, consent)],
            ASK_FIO:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
            ASK_EMAIL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            ASK_GENDER:  [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_apply)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        allow_reentry=True,  # ← можно снова /start в процессе
    )
    app.add_handler(conv)

    app.add_handler(CommandHandler("help", help_cmd))

    # админ
    app.add_handler(CommandHandler("inbox", inbox_cmd))
    app.add_handler(CommandHandler("find", find_cmd))
    app.add_handler(CommandHandler("set_status", set_status_cmd))
    app.add_handler(CommandHandler("export_csv", export_csv_cmd))
    app.add_handler(CommandHandler("export", export_alias_cmd))  # ← старая кнопка

    return app

def main() -> None:
    app = build_app()
    log.info("Бот запускается…")
    app.run_polling(close_loop=False)
    log.info("Бот остановлен.")

if __name__ == "__main__":
    main()
