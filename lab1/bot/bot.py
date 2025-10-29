# lab1/bot/bot.py
# Бот платформы «имяребенка.рф»
# Сценарий: приветствие → согласие → пол → распространённость → главный критерий (текст) → e-mail (валидация) → успех + кнопка.
# Данные пишутся строками JSON в lab1/data/leads.json

import os
import re
import json
import time
import logging
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ---------- конфигурация ----------
load_dotenv()
BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
COURSE_URL = os.getenv("COURSE_URL", "https://example.com/")
DATA_PATH  = Path(os.getenv("DATA_PATH", "lab1/data/leads.json"))
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("imyarj-bot")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# состояния
S_CONSENT, S_GENDER, S_POPULARITY, S_CRITERION, S_EMAIL = range(5)

# in-memory форма
FORM: dict[int, dict] = {}

def save_record(uid: int, rec: dict) -> None:
    """Пишем одну запись в JSONL (по строке на запись). Для ЛР1 этого достаточно."""
    rec = dict(rec)
    rec.update({"uid": uid, "ts": int(time.time())})
    DATA_PATH.touch(exist_ok=True)
    with DATA_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ---------- клавиатуры ----------
def kb_start():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Продолжить", callback_data="go")],
        [InlineKeyboardButton("Перейти на сайт", url=COURSE_URL)]
    ])

def kb_consent():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Согласен", callback_data="consent_yes"),
         InlineKeyboardButton("Не согласен", callback_data="consent_no")]
    ])

def kb_gender():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Мужской", callback_data="g_m"),
        InlineKeyboardButton("Женский", callback_data="g_f"),
        InlineKeyboardButton("Любой",   callback_data="g_a"),
    ]])

def kb_popularity():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Редкое",     callback_data="p_rare"),
        InlineKeyboardButton("Популярное", callback_data="p_pop"),
    ]])

# ---------- хэндлеры ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и стартовое меню."""
    uid = update.effective_user.id
    FORM[uid] = {"state": S_CONSENT, "consent": None}
    save_record(uid, {"type":"event","stage":"start"})
    text = (
        "Приветствуем вас в боте платформы «имяребенка.рф».\n"
        "Чтобы получить доступ к курсу «Как выбрать имя ребёнку?», ответьте, пожалуйста, на несколько вопросов."
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=kb_start())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=kb_start())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Команды: /start — начать заново, /help — помощь, /settings — статус согласия, /feedback — оставить отзыв.")

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    consent = FORM.get(uid, {}).get("consent")
    await update.message.reply_text(f"Статус согласия: {consent}. Чтобы изменить — выполните /start.")

async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Будем признательны за обратную связь: одним сообщением напишите, что бы вы хотели улучшить."
    )

async def on_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пишем отзыв только если сейчас не ждём criterion/email."""
    uid = update.effective_user.id
    state = FORM.get(uid, {}).get("state")
    if state not in (S_CRITERION, S_EMAIL):
        txt = (update.message.text or "").strip()
        if txt:
            save_record(uid, {"type":"feedback","text":txt})
            await update.message.reply_text("Спасибо! Мы учтём ваше мнение.")
            return False
    return True

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Свободные ответы: главный критерий и e-mail."""
    uid = update.effective_user.id
    state = FORM.get(uid, {}).get("state")

    # главный критерий — свободный текст
    if state == S_CRITERION:
        crit = (update.message.text or "").strip()
        if not crit:
            await update.message.reply_text("Пожалуйста, кратко опишите ваш главный критерий.")
            return
        FORM[uid]["criterion"] = crit
        FORM[uid]["state"] = S_EMAIL
        save_record(uid, {"type":"event","stage":"criterion_ok"})
        await update.message.reply_text(
            "Укажите адрес электронной почты. На него мы отправим ссылку на онлайн-курс и инструкции по доступу."
        )
        return

    # e-mail — с валидацией
    if state == S_EMAIL:
        email = (update.message.text or "").strip()
        if EMAIL_RE.match(email):
            FORM[uid]["email"] = email
            save_record(uid, {"type":"event","stage":"email_ok"})
            save_record(uid, {"type":"lead", **FORM[uid]})
            await update.message.reply_text(
                "Спасибо! Мы отправили инструкцию по доступу на указанную почту. "
                "Чтобы перейти к материалам прямо сейчас — нажмите на кнопку ниже.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Перейти на страницу курса", url=COURSE_URL)]]
                )
            )
            FORM[uid]["state"] = None
        else:
            await update.message.reply_text(
                "Похоже, в адресе есть ошибка. Пожалуйста, укажите почту в формате name@example.ru."
            )
        return

    # по умолчанию
    await update.message.reply_text("Чтобы начать, используйте /start.")

async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Все нажатия на кнопки."""
    q = update.callback_query
    uid = q.from_user.id
    FORM.setdefault(uid, {})
    await q.answer()

    try:
        data = q.data

        if data == "go":
            FORM[uid]["state"] = S_CONSENT
            await q.edit_message_text(
                "Подтвердите, пожалуйста, согласие на обработку введённых данных (ответы и адрес электронной почты). "
                "Данные используются исключительно для предоставления доступа к материалам.",
                reply_markup=kb_consent()
            )

        elif data == "consent_yes":
            FORM[uid]["consent"] = True
            FORM[uid]["state"] = S_GENDER
            save_record(uid, {"type":"event","stage":"consent_yes"})
            await q.edit_message_text("Укажите пол ребёнка.", reply_markup=kb_gender())

        elif data == "consent_no":
            save_record(uid, {"type":"event","stage":"consent_no"})
            await q.edit_message_text(
                "Хорошо. Вы можете перейти на сайт по кнопке ниже.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Перейти на сайт", url=COURSE_URL)]])
            )

        elif data in ("g_m","g_f","g_a"):
            FORM[uid]["gender"] = {"g_m":"male","g_f":"female","g_a":"any"}[data]
            FORM[uid]["state"] = S_POPULARITY
            save_record(uid, {"type":"event","stage":"gender"})
            await q.edit_message_text(
                "Какую распространённость имени вы рассматриваете?", reply_markup=kb_popularity()
            )

        elif data in ("p_rare","p_pop"):
            FORM[uid]["popularity"] = {"p_rare":"rare","p_pop":"popular"}[data]
            FORM[uid]["state"] = S_CRITERION
            save_record(uid, {"type":"event","stage":"popularity"})
            await q.edit_message_text(
                "Напишите одним-двумя предложениями, что для вас является главным критерием при выборе имени."
            )

        else:
            await q.edit_message_text("Неизвестное действие. Используйте /start.")
    except Exception as e:
        log.exception("Callback error: %s", e)
        await q.edit_message_text("Произошла ошибка. Пожалуйста, повторите попытку.")

def build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("Set BOT_TOKEN in .env")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("feedback", feedback_cmd))
    app.add_handler(CallbackQueryHandler(on_cb))
    # сначала пытаемся трактовать свободный текст как отзыв (если не ждём criterion/email)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_feedback_text), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text), group=1)
    return app

if __name__ == "__main__":
    build_app().run_polling()
