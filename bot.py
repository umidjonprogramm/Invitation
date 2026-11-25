import json
import os
import sqlite3
import time
import telebot
from telebot import types

BOT_TOKEN = os.getenv("8911257881:AAF3HDU2jk89GV5aNxmXL_a2tSx962ypgmw")
ADMIN_ID = 6713735399
CARD_NUMBER = "5614 6820 0945 5967"
CARD_HOLDER = "N. A"
PRICE = "15 000 so'm"
MINI_APP_URL = "https://umidjonprogramm.github.io/1nvitation/"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "invitations.db")

bot = telebot.TeleBot(BOT_TOKEN)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    is_paid INTEGER DEFAULT 0,
    waiting_receipt INTEGER DEFAULT 0
)
""")
conn.commit()


def is_admin(user_id):
    return int(user_id) == int(ADMIN_ID)


def has_access(user_id):
    if is_admin(user_id):
        return True
    cursor.execute("SELECT is_paid FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return bool(row and row[0] == 1)


def set_waiting_receipt(user_id, full_name, status):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
    cursor.execute(
        "UPDATE users SET waiting_receipt = ?, full_name = ? WHERE user_id = ?",
        (status, full_name, user_id)
    )
    conn.commit()


def grant_access(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)", (user_id, ""))
    cursor.execute("UPDATE users SET is_paid = 1, waiting_receipt = 0 WHERE user_id = ?", (user_id,))
    conn.commit()


def send_create_menu(chat_id, user_id):
    markup = types.InlineKeyboardMarkup()
    if MINI_APP_URL.startswith("https://"):
        web_btn = types.InlineKeyboardButton(
            text="💍 Taklifnoma yaratish (Mini App)",
            web_app=types.WebAppInfo(url=MINI_APP_URL)
        )
        markup.add(web_btn)
    url_btn = types.InlineKeyboardButton(text="🌐 Brauzerda ochish", url=MINI_APP_URL)
    markup.add(url_btn)

    role_text = "👑 Admin rejimi (BEPUL)" if is_admin(user_id) else "✅ To'lov tasdiqlangan"
    bot.send_message(
        chat_id,
        f"{role_text}\n\nTaklifnoma yaratish uchun quyidagi tugmani bosing:",
        reply_markup=markup
    )


def send_payment_info(chat_id, user_id, full_name):
    set_waiting_receipt(user_id, full_name, 1)
    text = (
        f"💍 *Onlayn to'y taklifnomasi yaratish*\n\n"
        f"Narxi: *{PRICE}*\n"
        f"Karta raqami: `{CARD_NUMBER}`\n"
        f"Karta egasi: *{CARD_HOLDER}*\n\n"
        f"1. Yuqoridagi kartaga *{PRICE}* o'tkazing.\n"
        f"2. To'lov cheki rasmini shu botga yuboring.\n"
        f"3. Admin tasdiqlagach, taklifnoma yaratish oynasi ochiladi."
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")


@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()

    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
    conn.commit()

    if is_admin(user_id) or has_access(user_id):
        send_create_menu(message.chat.id, user_id)
    else:
        send_payment_info(message.chat.id, user_id, full_name)


@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Bu buyruq faqat admin uchun.")
        return

    cursor.execute("SELECT COUNT(*) FROM users WHERE is_paid = 1")
    paid_count = cursor.fetchone()[0]
    bot.send_message(
        message.chat.id,
        f"👑 *Admin panel*\n\n"
        f"Siz uchun yaratish: *BEPUL*\n"
        f"To'lov qilgan foydalanuvchilar soni: *{paid_count} ta*",
        parse_mode="Markdown"
    )
    send_create_menu(message.chat.id, message.from_user.id)


@bot.message_handler(content_types=["photo"])
def handle_receipt_photo(message):
    user_id = message.from_user.id
    if is_admin(user_id):
        send_create_menu(message.chat.id, user_id)
        return

    full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    username = f"@{message.from_user.username}" if message.from_user.username else "yo'q"
    photo_id = message.photo[-1].file_id

    set_waiting_receipt(user_id, full_name, 0)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user_id}")
    )

    caption = (
        f"🧾 *Yangi to'lov cheki ({PRICE})*\n\n"
        f"Foydalanuvchi: *{full_name}*\n"
        f"Username: {username}\n"
        f"ID: `{user_id}`"
    )
    bot.send_photo(ADMIN_ID, photo_id, caption=caption, parse_mode="Markdown", reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ Chekingiz adminga yuborildi. Tasdiqlanishini kuting.")


@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")))
def handle_admin_decision(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Ruxsat yo'q.", show_alert=True)
        return

    action, target_str = call.data.split("_", 1)
    target_id = int(target_str)

    if action == "approve":
        grant_access(target_id)
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=call.message.caption + "\n\n✅ *TASDIQLANDI*",
            parse_mode="Markdown"
        )
        bot.send_message(target_id, "🎉 To'lovingiz tasdiqlandi! Endi taklifnoma yaratishingiz mumkin.")
        send_create_menu(target_id, target_id)
        bot.answer_callback_query(call.id, "Tasdiqlandi!")
    else:
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=call.message.caption + "\n\n❌ *RAD ETILDI*",
            parse_mode="Markdown"
        )
        bot.send_message(target_id, "❌ To'lov cheki tasdiqlanmadi. Qayta 15 000 so'm o'tkazib, aniq chek yuboring.")
        bot.answer_callback_query(call.id, "Rad etildi.")


@bot.message_handler(content_types=["web_app_data"])
def handle_web_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        groom = data.get("groom", "")
        bride = data.get("bride", "")
        link = data.get("url", "")
        bot.send_message(
            message.chat.id,
            f"💍 *{groom} va {bride}* taklifnomasi tayyor!\n\nHavola:\n{link}",
            parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(message.chat.id, "✅ Taklifnoma ma'lumotlari qabul qilindi.")


@bot.message_handler(func=lambda msg: True)
def handle_other_text(message):
    user_id = message.from_user.id
    full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    if has_access(user_id):
        send_create_menu(message.chat.id, user_id)
    else:
        send_payment_info(message.chat.id, user_id, full_name)


if __name__ == "__main__":
    print("Bot ishga tushdi...")
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print("Polling xatosi:", e)
            time.sleep(5)