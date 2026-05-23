
import os
import threading
import sqlite3
import asyncio
from datetime import datetime, timedelta
from collections import Counter



from flask import Flask

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN")



ADMIN_IDS = [1288830602]
ADMIN_PASSWORD = "876543210"

MASTER_INFO = {
    "Анна": {
        "photo": "https://i.postimg.cc/5yc6PjvJ/nail-2.jpg",
        "description": "💅 Анна\n✨ Мастер маникюра\n⭐️ Опыт: 5 років"
    },

    "Мария": {
        "photo": "https://i.postimg.cc/6Qg33TMV/nail-1.jpg",
        "description": "💅 Мария\n✨ Мастер маникюра\n⭐️ Опыт: 3 роки"
    },

    "София": {
        "photo": "https://i.postimg.cc/4ybNBPsL/nail-3.jpg",
        "description": "💅 София\n✨ Мастер маникюра\n⭐️ Опыт: 4 роки"
    }
}
DB_FILE = "nailsalon.db"

NAME, SERVICE, MASTER, DAY, TIME, COMMENT, CONFIRM, RESCHEDULE_DAY, RESCHEDULE_TIME, CONTACT_ADMIN, ADMIN_REPLY, ADMIN_CANCEL_COMMENT = range(12)



def kb(buttons):
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def back_kb(buttons):
    return ReplyKeyboardMarkup(buttons + [["⬅️ Назад"]], resize_keyboard=True)


def main_menu_kb():
    return kb([
        ["📝 Записаться"],
        ["📋 Мои записи"],
        ["💬 Связаться с администратором"],
        ["📞 Контакты"]
    ])


def admin_kb():
    return kb([
        ["📋 Список записей", "📊 Аналитика"],
        ["🕒 Занятые слоты"],
        ["❌ Удалить запись", "🧹 Очистить всё"],
        ["⚙️ Настройки"],
        ["🚪 Выйти из админки"],
    ])

def contacts_kb():
    return kb([
        ["📍 Адрес"],
        ["📞 Позвонить"],
        ["🌐 Соцсети"],
        ["⬅️ Назад в меню"]
    ])

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    service TEXT,
    master TEXT,
    date TEXT,
    time TEXT,
    comment TEXT,
    reminded INTEGER DEFAULT 0
)
""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        price TEXT,
        duration TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS masters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS master_profiles (
        master TEXT PRIMARY KEY,
        photo TEXT,
        description TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master TEXT,
    date TEXT,
    time TEXT
)
""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

    default_settings = {
    "phone": "+380 99 123 45 67",
    "address": "г. Киев, ул. Примерная 10",
    "socials": "Instagram: @nailstudio\nFacebook: -\nTikTok: -\nTelegram: -"
}

    for key, value in default_settings.items():
        cur.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )

    cur.execute("SELECT COUNT(*) FROM masters")
    masters_count = cur.fetchone()[0]

    if masters_count == 0:
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("Анна",))
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("Мария",))
        cur.execute("INSERT INTO masters (name) VALUES (?)", ("София",))

    cur.execute("SELECT COUNT(*) FROM services")
    services_count = cur.fetchone()[0]

    if services_count == 0:
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

        cur.execute(
            "INSERT INTO services (name, price, duration) VALUES (?, ?, ?)",
            ("Педикюр + покрытие", "1100 грн", "100 мин")
        )

        cur.execute(
            "INSERT INTO services (name, price, duration) VALUES (?, ?, ?)",
            ("Зняття покрытие", "200 грн", "20 мин")
        )

    cur.execute("SELECT COUNT(*) FROM schedule")
    schedule_count = cur.fetchone()[0]

    if schedule_count == 0:
        today = datetime.now()

        default_schedule = []

        for i in range(14):
            current_date = today + timedelta(days=i)

            date_str = current_date.strftime("%d.%m.%Y")

            default_schedule.append(("Анна", date_str, "10:00"))
            default_schedule.append(("Анна", date_str, "12:00"))

            default_schedule.append(("Мария", date_str, "11:00"))
            default_schedule.append(("Мария", date_str, "13:00"))

            default_schedule.append(("София", date_str, "14:00"))
            default_schedule.append(("София", date_str, "16:00"))

        cur.executemany(
            "INSERT INTO schedule (master, date, time) VALUES (?, ?, ?)",
            default_schedule
        )
    try:
        cur.execute("ALTER TABLE appointments ADD COLUMN comment TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def get_all_records():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, name, service, master, date, time, comment FROM appointments ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_records(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, name, service, master, date, time, comment FROM appointments WHERE user_id=? ORDER BY id",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_record(record_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, name, service, master, date, time, comment
        FROM appointments
        WHERE id=?
        """,
        (record_id,)
    )

    row = cur.fetchone()

    conn.close()
    return row

def add_record(user_id, name, service, master, date, time, comment):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO appointments 
        (user_id, name, service, master, date, time, comment, reminded) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, name, service, master, date, time, comment, 0)
    )

    conn.commit()
    conn.close()





def update_record_time(record_id, date, time):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "UPDATE appointments SET date=?, time=?, reminded=0 WHERE id=?",
        (date, time, record_id)
    )
    conn.commit()
    conn.close()


def delete_record(record_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM appointments WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
def mark_reminded(record_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "UPDATE appointments SET reminded=1 WHERE id=?",
        (record_id,)
    )

    conn.commit()
    conn.close()


def get_unreminded_records():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, name, service, master, date, time, comment 
        FROM appointments 
        WHERE reminded=0
        """
    )

    rows = cur.fetchall()
    conn.close()

    return rows

def clear_records():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM appointments")
    conn.commit()
    conn.close()

def delete_old_records():
    records = get_all_records()
    now = datetime.now()

    for record in records:
        record_id, user_id, name, service, master, date, time, comment = record

        try:
            record_datetime = get_next_record_datetime(date, time)
        except ValueError:
            continue

        if record_datetime < now:
            delete_record(record_id)

def delete_old_schedule():
    schedule = get_schedule()
    now = datetime.now()

    for item in schedule:
        schedule_id, master, date, time = item

        try:
            schedule_datetime = get_next_record_datetime(date, time)
        except ValueError:
            continue

        if schedule_datetime < now:
            delete_schedule(schedule_id)

def get_services():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT id, name, price, duration FROM services ORDER BY id")
    rows = cur.fetchall()

    conn.close()
    return rows


def add_service(name, price, duration):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO services (name, price, duration) VALUES (?, ?, ?)",
        (name, price, duration)
    )

    conn.commit()
    conn.close()


def delete_service(service_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("DELETE FROM services WHERE id=?", (service_id,))

    conn.commit()
    conn.close()

def get_masters():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM masters ORDER BY id")
    rows = cur.fetchall()

    conn.close()
    return rows


def add_master(name):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO masters (name) VALUES (?)",
        (name,)
    )

    conn.commit()
    conn.close()


def delete_master(master_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("DELETE FROM masters WHERE id=?", (master_id,))

    conn.commit()
    conn.close()

def get_schedule():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, master, date, time FROM schedule ORDER BY master, date, time"
    )

    rows = cur.fetchall()

    conn.close()
    return rows


def add_schedule(master, day, time):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO schedule (master, date, time) VALUES (?, ?, ?)",
        (master, day, time)
    )

    conn.commit()
    conn.close()


def delete_schedule(schedule_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM schedule WHERE id=?",
        (schedule_id,)
    )

    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()

    conn.close()

    return row[0] if row else ""


def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )

    conn.commit()
    conn.close()

def get_master_profile(master):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT photo, description FROM master_profiles WHERE master=?",
        (master,)
    )

    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "photo": row[0],
            "description": row[1]
        }

    return MASTER_INFO.get(master)


def set_master_profile(master, photo, description):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO master_profiles (master, photo, description)
        VALUES (?, ?, ?)
        """,
        (master, photo, description)
    )

    conn.commit()
    conn.close()

def get_master_dates_from_db(master):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT DISTINCT date FROM schedule WHERE master=? ORDER BY date",
        (master,)
    )

    rows = cur.fetchall()

    conn.close()

    return [row[0] for row in rows]

def get_master_times_from_db(master, day):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT time FROM schedule WHERE master=? AND date=? ORDER BY time",
        (master, day)
    )

    rows = cur.fetchall()

    conn.close()

    return [row[0] for row in rows]

def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_admin_logged(context):
    return context.user_data.get("admin_logged") is True

def settings_kb():
    return kb([
        ["💅 Услуги"],
        ["👤 Мастера"],
        ["📅 Расписание"],
        ["⬅️ Назад"]
    ])

def get_free_times(master, day, exclude_id=None):
    all_times = get_master_times_from_db(master, day)
    records = get_all_records()

    busy = []

    for record in records:
        record_id, _, _, _, rec_master, rec_day, rec_time, comment = record

        if exclude_id is not None and record_id == exclude_id:
            continue

        if rec_master == master and rec_day == day:
            busy.append(rec_time)

    return [t for t in all_times if t not in busy]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    context.user_data.clear()

    print(f"NEW USER: {update.message.from_user.full_name} | ID: {user_id}")
    
    if is_admin(user_id):
        if is_admin_logged(context):
            await update.message.reply_text(
                "⚙️ Админ-панель:",
                reply_markup=admin_kb()
            )
        else:
            context.user_data["waiting_password"] = True

            await update.message.reply_text(
                "Введите пароль администратора:"
            )

        return
    

    
    await update.message.reply_text(
        "💅 Добро пожаловать в Nail Studio\n\n"
        "✨ Онлайн запись 24/7\n"
        "💖 Маникюр и педикюр",
        reply_markup=main_menu_kb()
    )

    return ConversationHandler.END

async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери нужный раздел:",
        reply_markup=contacts_kb()
    )


async def contact_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📍 Адрес":
        await update.message.reply_text(
            f"📍 Адрес:\n{get_setting('address')}"
        )

    elif text == "📞 Позвонить":
        await update.message.reply_text(
            f"📞 Телефон:\n{get_setting('phone')}"
        )

    elif text == "🌐 Соцсети":
        await update.message.reply_text(
            f"🌐 Соцсети:\n{get_setting('socials')}"
        )

    elif text == "⬅️ Назад в меню":
        if is_admin(update.message.from_user.id) and is_admin_logged(context):
            await update.message.reply_text(
                "⚙️ Админ-панель:",
                reply_markup=admin_kb()
            )
        else:
            await update.message.reply_text(
                "Главное меню:",
                reply_markup=main_menu_kb()
            )

async def begin_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Введите своё имя:",
        reply_markup=back_kb([])
    )

    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END

    context.user_data["name"] = update.message.text

    services = get_services()

    if not services:
        await update.message.reply_text("Пока нет доступных услуг.")
        return ConversationHandler.END

    keyboard = [[service[1]] for service in services]

    await update.message.reply_text(
        "Выбери услугу:",
        reply_markup=back_kb(keyboard)
    )

    return SERVICE

async def get_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "Введите своё имя:",
            reply_markup=back_kb([])
        )
        return NAME

    service = update.message.text
    services = get_services()

    service_names = [s[1] for s in services]

    if service not in service_names:
        await update.message.reply_text("Выбери услугу кнопкой.")
        return SERVICE

    context.user_data["service"] = service

    selected_service = None

    for s in services:
        if s[1] == service:
            selected_service = s
            break

    masters = get_masters()

    if not masters:
        await update.message.reply_text("Пока нет доступных мастеров.")
        return ConversationHandler.END

    keyboard = [[m[1]] for m in masters]

    await update.message.reply_text(
        f"Услуга: {selected_service[1]}\n"
        f"Цена: {selected_service[2]}\n"
        f"Длительность: {selected_service[3]}\n\n"
        f"Выбери мастера:",
        reply_markup=back_kb(keyboard)
    )

    return MASTER

async def get_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        services = get_services()
        keyboard = [[s[1]] for s in services]

        await update.message.reply_text(
            "Выбери услугу:",
            reply_markup=back_kb(keyboard)
        )

        return SERVICE

    master = update.message.text
    masters = get_masters()
    master_names = [m[1] for m in masters]

    if master not in master_names:
        await update.message.reply_text("Выбери мастера кнопкой.")
        return MASTER

    context.user_data["master"] = master
    master_info = get_master_profile(master)

    if master_info:
        try:
            await update.message.reply_photo(
            photo=master_info["photo"],
            caption=master_info["description"]
        )
        except Exception as e:
            print(f"Ошибка фото мастера: {e}")
            await update.message.reply_text(master_info["description"])

    dates = get_master_dates_from_db(master)

    if not dates:
        await update.message.reply_text(
            "У этого мастера пока нет расписания."
        )
        return ConversationHandler.END

    keyboard = [[d] for d in dates]

    await update.message.reply_text(
        "Выбери дату:",
        reply_markup=back_kb(keyboard)
    )

    return DAY

async def get_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        masters = get_masters()
        keyboard = [[m[1]] for m in masters]

        await update.message.reply_text(
            "Выбери мастера:",
            reply_markup=back_kb(keyboard)
        )
        return MASTER

    date = update.message.text
    master = context.user_data["master"]

    dates = get_master_dates_from_db(master)

    if date not in dates:
        await update.message.reply_text("У этого мастера нет такой рабочей даты.")
        return DAY

    context.user_data["date"] = date

    free_times = get_free_times(master, date)

    if not free_times:
        await update.message.reply_text("На эту дату свободного времени нет. Выбери другую дату.")
        return DAY

    keyboard = [[t] for t in free_times]

    await update.message.reply_text(
        "Выбери время:",
        reply_markup=back_kb(keyboard)
    )

    return TIME


async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        master = context.user_data["master"]
        days = get_master_dates_from_db(master)
        keyboard = [[d] for d in days]
        await update.message.reply_text(
            "Выбери дату:",
            reply_markup=back_kb(keyboard)
        )

        return DAY

    time = update.message.text
    master = context.user_data["master"]
    date = context.user_data["date"]

    free_times = get_free_times(master, date)

    if time not in free_times:
        await update.message.reply_text("Это время уже занято или недоступно. Выбери другое.")
        return TIME

    context.user_data["time"] = time

    name = context.user_data["name"]
    service = context.user_data["service"]

    await update.message.reply_text(
    "💬 Добавь комментарий к записи или нажми 'Пропустить':",
    reply_markup=kb([
        ["⏭ Пропустить"],
        ["⬅️ Назад"]
    ])
    )

    return COMMENT

async def booking_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        master = context.user_data["master"]
        date = context.user_data["date"]

        free_times = get_free_times(master, date)
        keyboard = [[t] for t in free_times]

        await update.message.reply_text(
            "Выбери свободное время:",
            reply_markup=back_kb(keyboard)
        )

        return TIME

    if text == "⏭ Пропустить":
        context.user_data["comment"] = "Без комментария"
    else:
        context.user_data["comment"] = text

    await update.message.reply_text(
        f"Проверь запись:\n\n"
        f"Имя: {context.user_data['name']}\n"
        f"Услуга: {context.user_data['service']}\n"
        f"Мастер: {context.user_data['master']}\n"
        f"Дата: {context.user_data['date']}\n"
        f"Время: {context.user_data['time']}\n"
        f"Комментарий: {context.user_data['comment']}\n\n"
        f"Подтверждаем запись?",
        reply_markup=kb([
            ["✅ Подтвердить"],
            ["⬅️ Назад"],
            ["❌ Отменить"]
        ])
    )

    return CONFIRM

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        master = context.user_data["master"]
        date = context.user_data["date"]

        free_times = get_free_times(master, date)
        keyboard = [[t] for t in free_times]

        await update.message.reply_text(
            "Выбери свободное время:",
            reply_markup=back_kb(keyboard)
        )

        return TIME

    if text == "❌ Отменить":
        await update.message.reply_text(
            "Запись отменена.",
            reply_markup=main_menu_kb()
        )

        return ConversationHandler.END

    if text != "✅ Подтвердить":
        await update.message.reply_text("Нажми кнопку подтверждения.")
        return CONFIRM

    user_id = update.message.from_user.id
    data = context.user_data

    add_record(
        user_id,
        data["name"],
        data["service"],
        data["master"],
        data["date"],
        data["time"],
        data.get("comment", "Без комментария")
    )

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"📌 Новая запись:\n\n"
                f"Имя: {data['name']}\n"
                f"Услуга: {data['service']}\n"
                f"Мастер: {data['master']}\n"
                f"Дата: {data['date']}\n"
                f"Время: {data['time']}"
            )
        )

    if is_admin(user_id) and is_admin_logged(context):
        menu = admin_kb()
    else:
        menu = main_menu_kb()

    await update.message.reply_text(
        "✅ Запись подтверждена!",
        reply_markup=menu
    )

    return ConversationHandler.END

def get_next_record_datetime(date_str, time_str):
    date_obj = datetime.strptime(date_str, "%d.%m.%Y")

    hour, minute = map(int, time_str.split(":"))

    record_datetime = date_obj.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    return record_datetime

async def reminder_checker(app):
    while True:
        records = get_unreminded_records()
        now = datetime.now()

        for record in records:
            record_id, user_id, name, service, master, date, time, comment = record

            try:
                record_datetime = get_next_record_datetime(date, time)
            except ValueError:
                continue

            time_diff = (record_datetime - now).total_seconds()

            # Напоминание только примерно за 1 час до записи
            if 3500 <= time_diff <= 3600:
                try:
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"⏰ Напоминание!\n\n"
                            f"Через час у тебя запись:\n"
                            f"{service} | {master} | {date} | {time}"
                        )
                    )

                    mark_reminded(record_id)

                except Exception as e:
                    print(f"Ошибка напоминания: {e}")

        await asyncio.sleep(60)

async def old_records_cleaner(app):
    while True:
        delete_old_records()
        delete_old_schedule()

        await asyncio.sleep(3600)

async def show_my_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    records = get_user_records(user_id)

    if not records:
        await update.message.reply_text(
            "У тебя пока нет записей.",
            reply_markup=main_menu_kb()
        )
        return

    message = "📋 Твои записи:\n\n"
    keyboard = []

    for record in records:
        record_id, user_id, name, service, master, date, time, comment = record

        message += f"{record_id}. {service} | {master} | {date} | {time}\n"
        keyboard.append([f"🔁 Перенести {record_id}"])
        keyboard.append([f"❌ Отменить {record_id}"])

    keyboard.append(["⬅️ Назад"])

    await update.message.reply_text(
        message,
        reply_markup=kb(keyboard)
    )

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=main_menu_kb()
    )

async def start_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Напиши сообщение в формате:\n\n"
        "Имя | сообщение\n\n"
        "Например:\n"
        "Артем | Хочу перенести запись",
        reply_markup=back_kb([])
    )

    return CONTACT_ADMIN


async def send_message_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END

    text = update.message.text

    if "|" not in text:
        await update.message.reply_text(
            "Неверный формат.\n\n"
            "Пиши так:\n"
            "Имя | сообщение"
        )
        return CONTACT_ADMIN

    client_name, client_message = text.split("|", 1)

    client_name = client_name.strip()
    client_message = client_message.strip()

    if not client_name or not client_message:
        await update.message.reply_text(
            "Имя и сообщение не могут быть пустыми."
        )
        return CONTACT_ADMIN

    user = update.message.from_user

    records = get_user_records(user.id)

    if records:
        status = "✅ Клиент уже записан"
        appointments_text = ""

        for record in records:
            record_id, user_id, name, service, master, date, time, comment = record
            appointments_text += (
                f"\n№{record_id}: "
                f"{service} | {master} | {date} | {time}"
            )
    else:
        status = "⚪ Клиент пока не записан"
        appointments_text = "\nУ клиента нет записей"

    username = f"@{user.username}" if user.username else "Нет"

    for admin_id in ADMIN_IDS:
         await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"💬 Новое сообщение от клиента\n\n"
                f"{status}\n"
                f"{appointments_text}\n\n"
                f"👤 Клиент:\n"
                f"Имя: {client_name}\n"
                f"Telegram: {user.full_name}\n"
                f"Username: {username}\n"
                f"User ID: {user.id}\n\n"
                f"✉️ Сообщение:\n"
                f"{client_message}"
            ),
            reply_markup=kb([
                [f"💬 Ответить {user.id}"]
            ])
        )

    await update.message.reply_text(
        "✅ Сообщение отправлено администратору.",
        reply_markup=main_menu_kb()
    )

    return ConversationHandler.END

async def start_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if not is_admin(user_id):
        return ConversationHandler.END

    text = update.message.text

    try:
        client_id = int(text.split()[-1])
    except ValueError:
        await update.message.reply_text("Ошибка ответа.")
        return ConversationHandler.END

    context.user_data["reply_client_id"] = client_id

    await update.message.reply_text(
        "Напиши ответ клиенту:",
        reply_markup=back_kb([])
    )

    return ADMIN_REPLY


async def send_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "Админ-панель:",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    client_id = context.user_data.get("reply_client_id")

    if not client_id:
        await update.message.reply_text("Клиент не найден.")
        return ConversationHandler.END

    text = update.message.text

    try:
        await context.bot.send_message(
            chat_id=client_id,
            text=(
                f"💬 Ответ администратора:\n\n"
                f"{text}"
            )
        )

        await update.message.reply_text(
            "✅ Ответ отправлен.",
            reply_markup=admin_kb()
        )

    except Exception as e:
        await update.message.reply_text(
            f"Ошибка отправки:\n{e}",
            reply_markup=admin_kb()
        )

    return ConversationHandler.END

async def admin_cancel_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        context.user_data.pop("admin_cancel_record_id", None)

        await update.message.reply_text(
            "⚙️ Админ-панель:",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    record_id = context.user_data.get("admin_cancel_record_id")

    if not record_id:
        await update.message.reply_text(
            "Запись не найдена.",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    record = get_record(record_id)

    if not record:
        await update.message.reply_text(
            "Запись уже удалена.",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    record_id, user_id, name, service, master, date, time, comment = record

    if text == "Без комментария":
        admin_comment = "Без комментария"
    else:
        admin_comment = text.strip()

    delete_record(record_id)

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"❌ Ваша запись отменена администратором.\n\n"
                f"💈 Услуга: {service}\n"
                f"👤 Мастер: {master}\n"
                f"📅 Дата: {date}\n"
                f"🕒 Время: {time}\n\n"
                f"💬 Комментарий администратора:\n"
                f"{admin_comment}"
            ),
            reply_markup=kb([
                [f"💬 Связаться с администратором"]
            ])
        )
    except Exception as e:
        print(f"Ошибка сообщения клиенту об отмене: {e}")

    context.user_data.pop("admin_cancel_record_id", None)

    await update.message.reply_text(
        "✅ Запись отменена, клиенту отправлено сообщение.",
        reply_markup=admin_kb()
    )

    return ConversationHandler.END

async def cancel_user_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    try:
        record_id = int(text.split()[-1])
    except ValueError:
        await update.message.reply_text("Ошибка отмены записи.")
        return

    record = get_record(record_id)

    if not record or record[1] != user_id:
        await update.message.reply_text("Эта запись не найдена.")
        return

    record_id, _, name, service, master, day, time, comment = record

    delete_record(record_id)

    await update.message.reply_text(
        f"❌ Запись отменена:\n\n"
        f"{service} | {master} | {day} | {time}",
        reply_markup=main_menu_kb()
    )

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"❌ Клиент отменил запись:\n\n"
                f"Имя: {name}\n"
                f"Услуга: {service}\n"
                f"Мастер: {master}\n"
                f"День: {day}\n"
                f"Время: {time}"
            )
        )


async def start_reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    try:
        record_id = int(text.split()[-1])
    except ValueError:
        return ConversationHandler.END

    record = get_record(record_id)

    if not record or record[1] != user_id:
        await update.message.reply_text("Эта запись не найдена.")
        return ConversationHandler.END

    context.user_data["reschedule_id"] = record_id
    context.user_data["reschedule_master"] = record[4]

    master = record[4]
    dates = get_master_dates_from_db(master)
    keyboard = [[d] for d in dates]

    await update.message.reply_text(
        f"Перенос записи №{record_id}\n"
        f"Выбери новую дату:",
        reply_markup=back_kb(keyboard)
    )

    return RESCHEDULE_DAY


async def reschedule_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await show_my_records(update, context)
        return ConversationHandler.END

    day = update.message.text
    master = context.user_data["reschedule_master"]

    dates = get_master_dates_from_db(master)

    if day not in dates:
        await update.message.reply_text("У этого мастера нет такой рабочей даты. Выбери другую дату.")
        return RESCHEDULE_DAY

    context.user_data["reschedule_date"] = day

    record_id = context.user_data["reschedule_id"]
    free_times = get_free_times(master, day, exclude_id=record_id)

    if not free_times:
        await update.message.reply_text(
            "Нет свободного времени на этот день. Выбери другую дату."
        )
        return RESCHEDULE_DAY

    keyboard = [[t] for t in free_times]

    await update.message.reply_text(
        "Выбери новое время:",
        reply_markup=back_kb(keyboard)
    )

    return RESCHEDULE_TIME


async def reschedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        master = context.user_data["reschedule_master"]
        dates = get_master_dates_from_db(master)
        keyboard = [[d] for d in dates]

        await update.message.reply_text(
            "Выбери новую дату:",
            reply_markup=back_kb(keyboard)
        )

        return RESCHEDULE_DAY

    time = update.message.text

    record_id = context.user_data["reschedule_id"]
    date = context.user_data["reschedule_date"]
    master = context.user_data["reschedule_master"]

    free_times = get_free_times(master, date, exclude_id=record_id)

    if time not in free_times:
        await update.message.reply_text("Это время недоступно. Выбери другое.")
        return RESCHEDULE_TIME

    update_record_time(record_id, date, time)

    await update.message.reply_text(
        f"✅ Запись перенесена!\n\n"
        f"Новая дата: {date}\n"
        f"Новое время: {time}",
        reply_markup=main_menu_kb()
    )

    return ConversationHandler.END


async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if is_admin(user_id) and context.user_data.get("waiting_password"):
        if text == ADMIN_PASSWORD:
            context.user_data["admin_logged"] = True
            context.user_data["waiting_password"] = False

            await update.message.reply_text(
                "✅ Админ-панель открыта:",
                reply_markup=admin_kb()
            )
        else:
            await update.message.reply_text("❌ Неверный пароль.")

        return

    if not is_admin(user_id) or not is_admin_logged(context):
        return
    
    if context.user_data.get("waiting_setting"):
        setting_key = context.user_data["waiting_setting"]

        if text == "⬅️ Назад":
            context.user_data.pop("waiting_setting", None)

            await update.message.reply_text(
                "⚙️ Админ-панель:",
                reply_markup=admin_kb()
            )
            return

        set_setting(setting_key, text)
        context.user_data.pop("waiting_setting", None)

        await update.message.reply_text(
            "✅ Данные обновлены.",
            reply_markup=admin_kb()
        )
        return
    
    if context.user_data.get("waiting_master_profile"):
        master = context.user_data["waiting_master_profile"]

        if text == "⬅️ Назад":
            context.user_data.pop("waiting_master_profile", None)

            await update.message.reply_text(
                "⚙️ Админ-панель:",
                reply_markup=admin_kb()
            )
            return

        if " | " not in text:
            await update.message.reply_text(
                "Неверный формат.\n\n"
                "Пиши так:\n"
                "ссылка_на_фото | описание мастера"
            )
            return

        photo, description = text.split(" | ", 1)

        photo = photo.strip()
        description = description.strip()

        if not photo or not description:
            await update.message.reply_text(
                "Фото и описание не могут быть пустыми."
            )
            return

        set_master_profile(master, photo, description)

        context.user_data.pop("waiting_master_profile", None)

        await update.message.reply_text(
            "✅ Фото и описание мастера обновлены.",
            reply_markup=admin_kb()
        )
        return

    if context.user_data.get("admin_cancel_record_id"):
        if text == "⬅️ Назад":
            context.user_data.pop("admin_cancel_record_id", None)

            await update.message.reply_text(
                "⚙️ Админ-панель:",
                reply_markup=admin_kb()
            )
            return

        record_id = context.user_data.get("admin_cancel_record_id")
        record = get_record(record_id)

        if not record:
            context.user_data.pop("admin_cancel_record_id", None)

            await update.message.reply_text(
                "Запись уже удалена.",
                reply_markup=admin_kb()
            )
            return

        record_id, client_id, name, service, master, date, time, comment = record

        if text == "Без комментария":
            admin_comment = "Без комментария"
        else:
            admin_comment = text.strip()

        delete_record(record_id)

        try:
            await context.bot.send_message(
                chat_id=client_id,
                text=(
                    f"❌ Ваша запись отменена администратором.\n\n"
                    f"💈 Услуга: {service}\n"
                    f"👤 Мастер: {master}\n"
                    f"📅 Дата: {date}\n"
                    f"🕒 Время: {time}\n\n"
                    f"💬 Комментарий администратора:\n"
                    f"{admin_comment}"
                ),
                reply_markup=kb([
                    ["💬 Связаться с администратором"]
                ])
            )
        except Exception as e:
            print(f"Ошибка сообщения клиенту: {e}")

        context.user_data.pop("admin_cancel_record_id", None)

        await update.message.reply_text(
            "✅ Запись отменена, клиенту отправлено сообщение.",
            reply_markup=admin_kb()
        )
        return

    if context.user_data.get("waiting_new_service"):
        if text == "⬅️ Назад":
            context.user_data["waiting_new_service"] = False
            await update.message.reply_text("⚙️ Настройки:", reply_markup=admin_kb())
            return

        parts = text.split(" | ")

        if len(parts) != 3:
            await update.message.reply_text(
                "Неверный формат.\n\nПиши так:\nСтрижка | 500 грн | 45 мин"
            )
            return

        name, price, duration = parts
        add_service(name, price, duration)
        context.user_data["waiting_new_service"] = False

        await update.message.reply_text("✅ Услуга добавлена.", reply_markup=admin_kb())
        return

    if context.user_data.get("waiting_new_master"):
        if text == "⬅️ Назад":
            context.user_data["waiting_new_master"] = False
            await update.message.reply_text("⚙️ Настройки:", reply_markup=admin_kb())
            return

        master_name = text.strip()

        if not master_name:
            await update.message.reply_text("Имя мастера не может быть пустым.")
            return

        add_master(master_name)
        context.user_data["waiting_new_master"] = False

        await update.message.reply_text("✅ Мастер добавлен.", reply_markup=admin_kb())
        return

    if context.user_data.get("waiting_new_schedule"):
        if text == "⬅️ Назад":
            context.user_data["waiting_new_schedule"] = False
            await update.message.reply_text("⚙️ Настройки:", reply_markup=admin_kb())
            return

        parts = text.split(" | ")

        if len(parts) != 3:
            await update.message.reply_text(
                "Неверный формат.\n\nПиши так:\nАртем | 12.05.2026 | 14:00"
            )
            return

        master, date, time = parts
        master = master.strip()
        date = date.strip()
        time = time.strip()

        master_names = [m[1] for m in get_masters()]

        if master not in master_names:
            await update.message.reply_text(
                "Нет такого мастера. Сначала добавь мастера в настройках."
            )
            return

        add_schedule(master, date, time)
        context.user_data["waiting_new_schedule"] = False

        await update.message.reply_text("✅ Расписание добавлено.", reply_markup=admin_kb())
        return

    records = get_all_records()

    if text == "📋 Список записей":
        if not records:
            await update.message.reply_text("Записей нет.", reply_markup=admin_kb())
            return

        message = "📋 Все записи:\n\n"

        for r in records:
            record_id, _, name, service, master, date, time, comment = r
            message += f"{record_id}. {name} | {service} | {master} | {date} | {time}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "❌ Удалить запись":
        if not records:
            await update.message.reply_text("Записей нет.", reply_markup=admin_kb())
            return

        keyboard = [[f"❌ Запис {r[0]}"] for r in records]
        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Выбери запись для отмены:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("❌ Запис "):
        try:
            record_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Ошибка удаления.", reply_markup=admin_kb())
            return

        record = get_record(record_id)

        if not record:
            await update.message.reply_text("Запись не найдена.", reply_markup=admin_kb())
            return

        context.user_data["admin_cancel_record_id"] = record_id

        await update.message.reply_text(
            "Напиши причину отмены для клиента или нажми 'Без комментария':",
            reply_markup=kb([
                ["Без комментария"],
                ["⬅️ Назад"]
            ])
        )
        return ADMIN_CANCEL_COMMENT

    elif text == "📊 Аналитика":
        if not records:
            await update.message.reply_text("Аналитики пока нет.", reply_markup=admin_kb())
            return

        now = datetime.now()
        today_str = now.strftime("%d.%m.%Y")

        normalized_records = []

        for r in records:
            record_id, client_id, name, service, master, date, time, comment = r

            try:
                record_datetime = get_next_record_datetime(date, time)
            except ValueError:
                continue

            normalized_records.append({
                "id": record_id,
                "client_id": client_id,
                "name": name,
                "service": service,
                "master": master,
                "date": date,
                "time": time,
                "comment": comment,
                "datetime": record_datetime
            })

        if not normalized_records:
            await update.message.reply_text("Аналитики пока нет.", reply_markup=admin_kb())
            return

        normalized_records = sorted(normalized_records, key=lambda r: r["datetime"])
        today_records = [r for r in normalized_records if r["date"] == today_str]

        masters_counter = Counter(r["master"] for r in normalized_records)
        services_counter = Counter(r["service"] for r in normalized_records)
        dates_counter = Counter(r["date"] for r in normalized_records)

        sorted_masters = sorted(masters_counter.items(), key=lambda x: x[1], reverse=True)
        sorted_services = sorted(services_counter.items(), key=lambda x: x[1], reverse=True)
        sorted_dates = sorted(
            dates_counter.items(),
            key=lambda x: get_next_record_datetime(x[0], "00:00")
        )

        nearest_record = normalized_records[0]

        if nearest_record["date"] == today_str:
            nearest_text = f"сегодня в {nearest_record['time']}"
        else:
            nearest_text = f"{nearest_record['date']} о {nearest_record['time']}"

        message = "📊 Аналитика\n\n"
        message += "━━━━━━━━━━━━━━\n"
        message += "📌 Всего\n"
        message += f"• Активных записей: {len(normalized_records)}\n"
        message += f"• Уникальных клиентов: {len(set(r['client_id'] for r in normalized_records))}\n"
        message += f"• Ближайшая запись: {nearest_text}\n\n"

        message += "━━━━━━━━━━━━━━\n"
        message += f"📅 Сегодня — {today_str}\n"
        message += f"• Записей: {len(today_records)}\n\n"

        if today_records:
            for r in today_records:
                message += (
                    f"🕒 {r['time']}\n"
                    f"👤 {r['master']}\n"
                    f"💈 {r['service']}\n"
                    f"🙋 Клиент: {r['name']}\n"
                )

                if r["comment"]:
                    message += f"💬 Комментарий: {r['comment']}\n"

                message += "\n"
        else:
            message += "На сегодня записей нет\n\n"

        message += "━━━━━━━━━━━━━━\n"
        message += "👤 Мастера\n\n"

        for i, (master, count) in enumerate(sorted_masters):
            if i == 0:
                message += f"🏆 {master} — {count} записей\n"
            else:
                message += f"• {master} — {count} записи\n"

        message += "\n━━━━━━━━━━━━━━\n"
        message += "💅 Услуги\n\n"

        for i, (service, count) in enumerate(sorted_services):
            if i == 0:
                message += f"🔥 {service} — {count}\n"
            else:
                message += f"• {service} — {count}\n"

        message += "\n━━━━━━━━━━━━━━\n"
        message += "📅 По датам\n\n"

        for date, count in sorted_dates[:7]:
            message += f"• {date} — {count} записи\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text in ["🕘 Занятые слоты", "🕒 Занятые слоты"]:
        if not records:
            await update.message.reply_text("Занятых слотов нет.", reply_markup=admin_kb())
            return

        message = "🕒 Занятые слоты:\n\n"

        for r in records:
            record_id, _, name, service, master, date, time, comment = r
            message += f"{record_id}. {master} — {date} {time} ({service})\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "🧹 Очистить всё":
        clear_records()
        await update.message.reply_text("🧹 Все записи удалены.", reply_markup=admin_kb())

    elif text == "⚙️ Настройки":
        await update.message.reply_text(
            "⚙️ Настройки:",
            reply_markup=kb([
                ["💅 Услуги"],
                ["👤 Мастера"],
                ["📅 Расписание"],
                ["🌐 Контакты и соцсети"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "💅 Услуги":
        await update.message.reply_text(
            "💅 Управление услугами:",
            reply_markup=kb([
                ["📋 Список услуг"],
                ["➕ Добавить услугу"],
                ["❌ Удалить услугу"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "📋 Список услуг":
        services = get_services()

        if not services:
            await update.message.reply_text("Услуг пока нет.", reply_markup=admin_kb())
            return

        message = "💅 Услуги:\n\n"

        for service in services:
            service_id, name, price, duration = service
            message += f"{service_id}. {name} | {price} | {duration}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "➕ Добавить услугу":
        context.user_data["waiting_new_service"] = True

        await update.message.reply_text(
            "Напиши новую услугу в формате:\n\n"
            "Название | Цена | Длительность\n\n"
            "Например:\n"
            "Маникюр | 600 грн | 60 мин",
            reply_markup=back_kb([])
        )

    elif text == "❌ Удалить услугу":
        services = get_services()

        if not services:
            await update.message.reply_text("Услуг пока нет.", reply_markup=admin_kb())
            return

        keyboard = []

        for service in services:
            service_id, name, _, _ = service
            keyboard.append([f"❌ Услуга {service_id}"])

        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Выбери услугу для удаления:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("❌ Услуга "):
        try:
            service_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Ошибка удаления.")
            return

        delete_service(service_id)

        await update.message.reply_text("✅ Услуга удалена.", reply_markup=admin_kb())

    elif text == "👤 Мастера":
        await update.message.reply_text(
            "👤 Управление мастерами:",
            reply_markup=kb([
                ["📋 Список мастеров"],
                ["➕ Добавить мастера"],
                ["❌ Удалить мастера"],
                ["🖼 Изменить фото/описание мастера"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "📋 Список мастеров":
        masters = get_masters()

        if not masters:
            await update.message.reply_text("Мастеров пока нет.", reply_markup=admin_kb())
            return

        message = "👤 Мастера:\n\n"

        for master in masters:
            master_id, name = master
            message += f"{master_id}. {name}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "➕ Добавить мастера":
        context.user_data["waiting_new_master"] = True

        await update.message.reply_text(
            "Напиши имя мастера.\n\n"
            "Например:\n"
            "Ігор",
            reply_markup=back_kb([])
        )

    elif text == "❌ Удалить мастера":
        masters = get_masters()

        if not masters:
            await update.message.reply_text("Мастеров пока нет.", reply_markup=admin_kb())
            return

        keyboard = []

        for master in masters:
            master_id, name = master
            keyboard.append([f"❌ Мастер {master_id}"])

        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Выбери мастера для удаления:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("❌ Мастер "):
        try:
            master_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Ошибка удаления.")
            return

        delete_master(master_id)

        await update.message.reply_text("✅ Мастер удален.", reply_markup=admin_kb())

    elif text == "🖼 Изменить фото/описание мастера":
        masters = get_masters()

        if not masters:
            await update.message.reply_text(
                "Мастеров пока нет.",
                reply_markup=admin_kb()
            )
            return

        keyboard = []

        for master in masters:
            master_id, name = master
            keyboard.append([f"🖼 Мастер {name}"])

        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Выбери мастера для редактирования:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("🖼 Мастер "):
        master_name = text.replace("🖼 Мастер ", "").strip()

        master_names = [m[1] for m in get_masters()]

        if master_name not in master_names:
            await update.message.reply_text(
                "Мастер не найден.",
                reply_markup=admin_kb()
            )
            return

        context.user_data["waiting_master_profile"] = master_name

        await update.message.reply_text(
            "Отправь новое фото и описание одним сообщением:\n\n"
            "ссылка_на_фото | описание мастера\n\n"
            "Приклад:\n"
            "https://i.postimg.cc/example.jpg | 👤 Артем\n"
            "💈 Барбер\n"
            "⭐️ Опыт: 5 років",
            reply_markup=back_kb([])
        )

    elif text == "📅 Расписание":
        await update.message.reply_text(
            "📅 Управление расписанием:",
            reply_markup=kb([
                ["📋 Список расписания"],
                ["➕ Добавить расписание"],
                ["❌ Удалить расписание"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "📋 Список расписания":
        schedule = get_schedule()

        if not schedule:
            await update.message.reply_text("Расписания пока нет.", reply_markup=admin_kb())
            return

        message = "📅 Расписание:\n\n"

        for item in schedule:
            schedule_id, master, date, time = item
            message += f"{schedule_id}. {master} | {date} | {time}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    elif text == "➕ Добавить расписание":
        context.user_data["waiting_new_schedule"] = True

        await update.message.reply_text(
            "Напиши расписание в формате:\n\n"
            "Мастер | Дата | Время\n\n"
            "Например:\n"
            "Артем | 12.05.2026 | 14:00",
            reply_markup=back_kb([])
        )

    elif text == "❌ Удалить расписание":
        schedule = get_schedule()

        if not schedule:
            await update.message.reply_text("Расписания пока нет.", reply_markup=admin_kb())
            return

        keyboard = []

        for item in schedule:
            schedule_id, master, date, time = item
            keyboard.append([f"❌ Расписание {schedule_id}"])

        keyboard.append(["⬅️ Назад"])

        await update.message.reply_text(
            "Выбери строку расписания для удаления:",
            reply_markup=kb(keyboard)
        )

    elif text.startswith("❌ Расписание "):
        try:
            schedule_id = int(text.split()[-1])
        except ValueError:
            await update.message.reply_text("Ошибка удаления.")
            return

        delete_schedule(schedule_id)

        await update.message.reply_text("✅ Расписание удалено.", reply_markup=admin_kb())

    elif text == "⬅️ Назад":
        await update.message.reply_text("⚙️ Админ-панель:", reply_markup=admin_kb())

    elif text == "🌐 Контакты и соцсети":
        await update.message.reply_text(
            "🌐 Управление контактами:",
            reply_markup=kb([
                ["📞 Изменить номер"],
                ["📍 Изменить адрес"],
                ["🌐 Изменить соцсети"],
                ["⬅️ Назад"]
            ])
        )

    elif text == "📞 Изменить номер":
        context.user_data["waiting_setting"] = "phone"

        await update.message.reply_text(
            "Напиши новый номер телефона:",
            reply_markup=back_kb([])
        )

    elif text == "📍 Изменить адрес":
        context.user_data["waiting_setting"] = "address"

        await update.message.reply_text(
            "Напиши новый адрес:",
            reply_markup=back_kb([])
        )

    elif text == "🌐 Изменить соцсети":
        context.user_data["waiting_setting"] = "socials"

        await update.message.reply_text(
            "Напиши соцсети в формате:\n\n"
            "Instagram: @name\n"
            "Facebook: link\n"
            "TikTok: @name\n"
            "Telegram: @name",
            reply_markup=back_kb([])
        )

    elif text == "🚪 Выйти из админки":
        context.user_data["admin_logged"] = False

        await update.message.reply_text(
            "Ты вышел из админки.",
            reply_markup=main_menu_kb()
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=main_menu_kb()
    )

    return ConversationHandler.END


web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Bot is running"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)


def main():
    if not TOKEN:
        raise RuntimeError("TOKEN is missing. Add TOKEN in Render Environment Variables.")

    init_db()

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    app = ApplicationBuilder().token(TOKEN).build()

    booking = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📝 Записаться$"), begin_booking)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_service)],
            MASTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_master)],
            DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_day)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_comment)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_booking)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    reschedule = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔁 Перенести \\d+$"), start_reschedule)
        ],
        states={
            RESCHEDULE_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reschedule_day)],
            RESCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reschedule_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    contact_admin = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💬 Связаться с администратором$"), start_contact_admin)
        ],
        states={
            CONTACT_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_to_admin)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_reply_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^💬 Ответить \\d+$"),
                start_admin_reply
            )
        ],
        states={
            ADMIN_REPLY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    send_admin_reply
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(CommandHandler("start", start))
   
    app.add_handler(CommandHandler("cancel", cancel))
    
    
   

    app.add_handler(booking)
    app.add_handler(reschedule)
    app.add_handler(contact_admin)
    app.add_handler(admin_reply_handler)
    app.add_handler(MessageHandler(filters.Regex("^📋 Мои записи$"), show_my_records))
    app.add_handler(
        MessageHandler(
            filters.Regex("^⬅️ Назад$") & ~filters.User(user_id=ADMIN_IDS),
            back_to_main_menu
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^❌ Отменить \\d+$"),
            cancel_user_record
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📞 Контакты$"),
            show_contacts
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^(📍 Адрес|📞 Позвонить|📸 Instagram)$"),
            contact_buttons
        )
    )

    app.add_handler(
    MessageHandler(
        filters.Regex("^(📍 Адрес|📞 Позвонить|🌐 Соцсети|⬅️ Назад в меню)$"),
        contact_buttons
    )
)

    app.add_handler(
        ConversationHandler(
            entry_points=[
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_IDS),
                    admin_buttons
                )
        ],
        states={
            ADMIN_CANCEL_COMMENT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_cancel_comment
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
)

    
    print("Бот работает...")

    app.job_queue.run_once(
        lambda context: asyncio.create_task(reminder_checker(app)),
        when=1
    )
    app.job_queue.run_once(
        lambda context: asyncio.create_task(old_records_cleaner(app)),
        when=5
    )
    app.run_polling()


if __name__ == "__main__":
    main()

