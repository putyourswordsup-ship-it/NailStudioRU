import os
import sqlite3
import threading

from flask import Flask
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TOKEN = os.getenv("TOKEN")

DB_FILE = "nailsalon.db"

ADMIN_IDS = [123456789]

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
                print(e)
                await update.message.reply_text(master_info["description"])

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT name, price, duration FROM services")
        services = cur.fetchall()
        conn.close()

        keyboard = []

        for service in services:
            name, price, duration = service
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
app_flask = Flask(__name__)


@app_flask.route("/")
def home():
    return "Bot is running"


def run_flask():
    app_flask.run(
        host="0.0.0.0",
        port=10000
    )


def main():
    init_db()

    from telegram.ext import ApplicationBuilder
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            buttons
        )
    )

    flask_thread = threading.Thread(target=run_flask)

    flask_thread.start()

    print("Bot started")

    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("STARTUP ERROR:")
        traceback.print_exc()
