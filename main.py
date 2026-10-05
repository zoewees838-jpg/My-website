import os
import sqlite3
import datetime
import hmac
import hashlib
import threading
import requests
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Read Environment Variables set on Render
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PORT = int(os.environ.get("PORT", 5000))

# ------------------- DATABASE SETUP -------------------
def init_db():
    conn = sqlite3.connect("rentals.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rentals (
            telegram_id INTEGER PRIMARY KEY,
            reference TEXT,
            status TEXT DEFAULT 'pending',
            expires_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def activate_rental(telegram_id: int, reference: str, days: int = 30):
    conn = sqlite3.connect("rentals.db")
    cursor = conn.cursor()
    expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
    cursor.execute('''
        INSERT OR REPLACE INTO rentals (telegram_id, reference, status, expires_at)
        VALUES (?, ?, 'active', ?)
    ''', (telegram_id, reference, expiry_date))
    conn.commit()
    conn.close()

def is_rental_active(telegram_id: int) -> bool:
    conn = sqlite3.connect("rentals.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT expires_at FROM rentals 
        WHERE telegram_id = ? AND status = 'active'
    ''', (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        expiry_date = datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S.%f")
        return datetime.datetime.now() < expiry_date
    return False

# ------------------- PAYSTACK UTILS -------------------
def create_paystack_url(email: str, telegram_id: int) -> str:
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "email": email,
        "amount": 150000,  # ₦1,500 in kobo
        "metadata": {"telegram_id": telegram_id}
    }
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if res.get("status"):
            return res["data"]["authorization_url"]
    except Exception as e:
        print("Paystack Error:", e)
    return ""

def send_telegram_message(telegram_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": telegram_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# ------------------- FLASK WEBHOOK SERVER -------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "AI Rental Bot Server is live!", 200

@app.route("/paystack-webhook", methods=["POST"])
def paystack_webhook():
    paystack_signature = request.headers.get("x-paystack-signature")
    computed_signature = hmac.new(
        PAYSTACK_SECRET_KEY.encode('utf-8'),
        request.data,
        hashlib.sha512
    ).hexdigest()

    if paystack_signature != computed_signature:
        return jsonify({"status": "invalid signature"}), 400

    event = request.json
    if event and event.get("event") == "charge.success":
        data = event["data"]
        telegram_id = data["metadata"]["telegram_id"]
        reference = data["reference"]

        # Activate rental for 30 days
        activate_rental(telegram_id, reference, days=30)

        # Notify user instantly on Telegram
        send_telegram_message(
            telegram_id,
            "🎉 **Payment Verified!**\n\nYour 30-day AI Tool rental is now **ACTIVE**. Tap 'Access AI Tool' in the bot menu to start."
        )
        return jsonify({"status": "success"}), 200

    return jsonify({"status": "ignored"}), 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ------------------- TELEGRAM BOT HANDLERS -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Rent AI Tool (₦1,500 / 30 Days)", callback_data="rent")],
        [InlineKeyboardButton("Access AI Tool", callback_data="use_tool")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to the **AI Tool Rental Portal**.\n\nRent full access to premium AI features for ₦1,500 per month.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id

    if query.data == "rent":
        email = f"user_{telegram_id}@telegram.com"
        pay_url = create_paystack_url(email, telegram_id)
        if pay_url:
            pay_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("Pay ₦1,500 via Paystack", url=pay_url)]
            ])
            await query.edit_message_text(
                "Click the link below to complete your rental payment:\n\nYour subscription activates automatically upon payment completion.",
                reply_markup=pay_button
            )
        else:
            await query.edit_message_text("Unable to generate payment link. Please check your API keys.")

    elif query.data == "use_tool":
        if is_rental_active(telegram_id):
            await query.edit_message_text("✅ **Access Granted!** Welcome to your AI Tool. Your 30-day rental pass is active.")
        else:
            renew_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("Rent Pass — ₦1,500", callback_data="rent")]
            ])
            await query.edit_message_text(
                "❌ **Access Denied**: You do not have an active rental pass.\n\nPlease subscribe to unlock access.",
                reply_markup=renew_button
            )

# ------------------- MAIN ENTRY POINT -------------------
if __name__ == "__main__":
    init_db()
    
    # Run Webhook server on background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Run Telegram Bot polling
    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(handle_button))
    
    print("Bot and Webhook server running...")
    telegram_app.run_polling()
