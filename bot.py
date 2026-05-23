import os
import sqlite3
import threading

from flask import Flask
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TOKEN = os.getenv("TOKEN")
DB_FILE = "nailsalon.db"

MASTER_INFO = {
    "Анна": {
        "photo": "https://i.postimg.cc/cLdyHp7N/nail-1.jpg",
        "description": "💅 Анна\n✨ Мастер маникюра\n⭐️ Опыт: 5 лет"
    },
    "Мария": {
        "photo": "https://i.postimg.cc/HxqFCRW9/nail-2.jpg",
        "description": "💅 Мария\n✨ Мастер маникюра\n⭐️ Опыт: 3 года"
    },
    "София": {
        "photo": "https://i.postimg.cc/65LgDMkb/nail-3.jpg",
        "description": "💅 София\n✨ Мастер маникюра\n⭐️ Опыт: 4 года"
    }
}


def kb(buttons):
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS masters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price TEXT,
        duration TEXT
    )
    """)

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM masters")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("Анна",))
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("Мария",))
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("София",))

    cur.execute("SELECT COUNT(*) FROM services")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO services (name, price, duration) VALUES (?, ?, ?)",
            ("Маникюр", "600 грн", "60 мин")
        )
        cur.execute(
            "INSERT INTO services (name, price, duration) VALUES (?, ?, ?)",
            ("Маникюр + покрытие", "900 грн", "90 мин")
        )
        cur.execute(
            "INSERT INTO services (name, price, duration) VALUES (?, ?, ?)",
            ("Педикюр", "800 грн", "75 мин")
        )

    conn.commit()
    conn.close()


def get_masters():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM masters")
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_services():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name, price, duration FROM services")
    rows = cur.fetchall()
    conn.close()
    return rows


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "💅 Добро пожаловать в Nail Studio\n\n"
        "✨ Онлайн запись 24/7\n"
        "💖 Маникюр и педикюр",
        reply_markup=kb([
            ["📅 Записаться"],
            ["📞 Контакты"]
        ])
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📅 Записаться":
        masters = get_masters()
        keyboard = [[master] for master in masters]
        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "👩 Выберите мастера:",
            reply_markup=kb(keyboard)
        )

    elif text in get_masters():
        context.user_data["master"] = text
        master_info = MASTER_INFO.get(text)

        if master_info:
            try:
                await update.message.reply_photo(
                    photo=master_info["photo"],
                    caption=master_info["description"]
                )
            except Exception as e:
                print(f"Photo error: {e}")
                await update.message.reply_text(master_info["description"])

        services = get_services()
        keyboard = []

        for name, price, duration in services:
            keyboard.append([f"{name} • {price} • {duration}"])

        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "💅 Выберите услугу:",
            reply_markup=kb(keyboard)
        )

    elif text == "📞 Контакты":
        await update.message.reply_text(
            "📍 Nail Studio\n"
            "📞 +380000000000\n"
            "📷 Instagram: @nailstudio"
        )

    elif text == "⬅️ Назад":
        await start(update, context)

    else:
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=kb([
                ["📅 Записаться"],
                ["📞 Контакты"]
            ])
        )


web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Bot is running"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)


def main():
    if not TOKEN:
        raise RuntimeError("TOKEN is missing")

    init_db()

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buttons))

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
