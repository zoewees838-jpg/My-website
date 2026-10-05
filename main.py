import datetime
import hashlib
import hmac
import os
import sqlite3
import threading
from flask import Flask, jsonify, request
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ------------------- CONFIGURATION & ENV VARIABLES -------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PORT = int(os.environ.get("PORT", 5000))

# UPDATED WITH YOUR LIVE RENDER WEB APP URL
DEFAULT_APP_URL = "https://nexora-telegram-bot-2j9e.onrender.com"
WEB_APP_URL = os.environ.get("WEB_APP_URL", DEFAULT_APP_URL)


# ------------------- DATABASE SETUP -------------------
def init_db():
    conn = sqlite3.connect("rentals.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rentals (
            telegram_id INTEGER PRIMARY KEY,
            reference TEXT,
            status TEXT DEFAULT 'pending',
            expires_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def activate_rental(telegram_id: int, reference: str, days: int = 30):
    conn = sqlite3.connect("rentals.db")
    cursor = conn.cursor()
    expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
    expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT OR REPLACE INTO rentals (telegram_id, reference, status, expires_at)
        VALUES (?, ?, 'active', ?)
    """,
        (telegram_id, reference, expiry_str),
    )
    conn.commit()
    conn.close()


def get_rental_expiry(telegram_id: int):
    conn = sqlite3.connect("rentals.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT expires_at FROM rentals 
        WHERE telegram_id = ? AND status = 'active'
    """,
        (telegram_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S.%f")
    return None


def is_rental_active(telegram_id: int) -> bool:
    expiry_date = get_rental_expiry(telegram_id)
    if expiry_date:
        return datetime.datetime.now() < expiry_date
    return False


# ------------------- PAYSTACK UTILS -------------------
def create_paystack_url(email: str, telegram_id: int) -> str:
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "amount": 150000,  # ₦1,500 in kobo
        "metadata": {"telegram_id": telegram_id},
    }
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if res.get("status"):
            return res["data"]["authorization_url"]
    except Exception as e:
        print("Paystack Error:", e)
    return ""


def send_telegram_message(
    telegram_id: int, text: str, reply_markup: dict = None
):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": telegram_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)


# ------------------- FLASK WEBHOOK & WEBAPP SERVER -------------------
app = Flask(__name__)


@app.route("/")
def home():
    return "AI Rental Bot Server is live!", 200


@app.route("/workspace")
def workspace():
    """Vibrant Red & Pink Nexora VIP AI Tools WebApp Dashboard"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
        <title>Nexora VIP AI Workspace</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Poppins', sans-serif;
            }
            body {
                background: linear-gradient(135deg, #0d0208 0%, #1a0513 50%, #2b081e 100%);
                color: #ffffff;
                min-height: 100vh;
                padding: 20px 15px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            .header {
                text-align: center;
                margin-bottom: 25px;
                width: 100%;
            }
            .badge {
                background: linear-gradient(90deg, #ff0055, #ff2a85);
                color: #fff;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 700;
                border-radius: 20px;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                box-shadow: 0 0 15px rgba(255, 0, 85, 0.6);
                display: inline-block;
                margin-bottom: 10px;
            }
            h1 {
                font-size: 24px;
                font-weight: 700;
                background: linear-gradient(90deg, #ff2a85, #ff73a8, #ff0055);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 6px;
            }
            p.subtitle {
                font-size: 13px;
                color: #d19bb8;
            }
            .container {
                width: 100%;
                max-width: 420px;
                display: flex;
                flex-direction: column;
                gap: 16px;
            }
            .card {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 42, 133, 0.3);
                border-radius: 16px;
                padding: 18px;
                backdrop-filter: blur(12px);
                box-shadow: 0 8px 32px 0 rgba(255, 0, 85, 0.15);
                transition: all 0.3s ease;
                display: flex;
                flex-direction: column;
            }
            .card:hover {
                border-color: #ff2a85;
                box-shadow: 0 8px 32px 0 rgba(255, 0, 85, 0.35);
                transform: translateY(-2px);
            }
            .card-header {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 10px;
            }
            .icon-box {
                width: 42px;
                height: 42px;
                border-radius: 12px;
                background: linear-gradient(135deg, #ff0055, #ff2a85);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
                box-shadow: 0 0 10px rgba(255, 0, 85, 0.5);
            }
            .card-title {
                font-size: 16px;
                font-weight: 600;
                color: #fff;
            }
            .card-desc {
                font-size: 12px;
                color: #b891a5;
                margin-bottom: 14px;
                line-height: 1.4;
            }
            .btn {
                width: 100%;
                padding: 12px;
                border: none;
                border-radius: 10px;
                background: linear-gradient(90deg, #ff0055, #ff2a85);
                color: white;
                font-size: 13px;
                font-weight: 600;
                text-align: center;
                text-decoration: none;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(255, 0, 85, 0.4);
                transition: all 0.2s ease;
                display: block;
            }
            .btn:active {
                transform: scale(0.98);
                box-shadow: 0 2px 8px rgba(255, 0, 85, 0.6);
            }
            .footer {
                margin-top: 30px;
                font-size: 11px;
                color: #7a4f66;
                text-align: center;
            }
        </style>
    </head>
    <body>

        <div class="header">
            <span class="badge">VIP Access Active</span>
            <h1>Nexora AI Workspace</h1>
            <p class="subtitle">Select a tool below to launch your session</p>
        </div>

        <div class="container">

            <!-- ChatGPT Card -->
            <div class="card">
                <div class="card-header">
                    <div class="icon-box">🤖</div>
                    <div class="card-title">ChatGPT / GPT-4o</div>
                </div>
                <div class="card-desc">Advanced reasoning, coding assistant, copywriter, and problem solver.</div>
                <a href="https://chatgpt.com" target="_blank" class="btn">Launch ChatGPT</a>
            </div>

            <!-- Image AI Card -->
            <div class="card">
                <div class="card-header">
                    <div class="icon-box">🎨</div>
                    <div class="card-title">Ideogram / Image AI</div>
                </div>
                <div class="card-desc">Generate high-definition AI artwork, logos, graphics, and design concepts.</div>
                <a href="https://ideogram.ai" target="_blank" class="btn">Launch Image AI</a>
            </div>

            <!-- Claude AI Card -->
            <div class="card">
                <div class="card-header">
                    <div class="icon-box">⚡</div>
                    <div class="card-title">Claude 3.5 Sonnet</div>
                </div>
                <div class="card-desc">Superior writing, deep long-context analysis, and complex code generation.</div>
                <a href="https://claude.ai" target="_blank" class="btn">Launch Claude AI</a>
            </div>

            <!-- Gemini Card -->
            <div class="card">
                <div class="card-header">
                    <div class="icon-box">✨</div>
                    <div class="card-title">Google Gemini Pro</div>
                </div>
                <div class="card-desc">Multimodal search integration, fast processing, and smart synthesis.</div>
                <a href="https://gemini.google.com" target="_blank" class="btn">Launch Gemini Pro</a>
            </div>

        </div>

        <div class="footer">
            Nexora AI Platform • Powered by Render & Telegram
        </div>

        <script>
            // Expand WebApp window to full height inside Telegram
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.ready();
                window.Telegram.WebApp.expand();
            }
        </script>
    </body>
    </html>
    """, 200


@app.route("/paystack-webhook", methods=["POST"])
def paystack_webhook():
    paystack_signature = request.headers.get("x-paystack-signature")
    computed_signature = hmac.new(
        PAYSTACK_SECRET_KEY.encode("utf-8"), request.data, hashlib.sha512
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

        # Calculate Expiry String for Message
        expiry_date = (
            datetime.datetime.now() + datetime.timedelta(days=30)
        ).strftime("%d %b, %Y")

        welcome_text = (
            f"✅ *Access Granted! Welcome to Nexora VIP.*\n\n"
            f"Your *30-Day Rental Pass* is active! Here is what you get:\n\n"
            f"🔓 *Unrestricted AI Access:* Full access to all Nexora AI features & tools.\n"
            f"⚡ *Priority Processing Speed:* High-priority queue for fast output.\n"
            f"🚫 *No Daily Limits or Cooldowns:* Zero usage caps or timers.\n"
            f"🌟 *VIP Features & Updates:* Instant access to new updates.\n"
            f"🛡️ *30-Day Validity:* Active until {expiry_date}.\n\n"
            f"👇 Tap the button below to launch your workspace and enjoy your access:"
        )

        # Open workspace seamlessly inside Telegram
        inline_keyboard = {
            "inline_keyboard": [[
                {"text": "🚀 Launch AI Workspace", "web_app": {"url": f"{WEB_APP_URL}/workspace"}}
            ]]
        }

        # Notify user instantly on Telegram
        send_telegram_message(telegram_id, welcome_text, reply_markup=inline_keyboard)
        return jsonify({"status": "success"}), 200

    return jsonify({"status": "ignored"}), 200


def run_flask():
    app.run(host="0.0.0.0", port=PORT)


# ------------------- TELEGRAM BOT HANDLERS -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "Rent AI Tool (₦1,500 / 30 Days)", callback_data="rent"
            )
        ],
        [InlineKeyboardButton("Access AI Tool", callback_data="use_tool")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to the *AI Tool Rental Portal*.\n\nRent full access to premium"
        " AI features for ₦1,500 per month.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id

    if query.data == "rent":
        email = f"user_{telegram_id}@telegram.com"
        pay_url = create_paystack_url(email, telegram_id)
        if pay_url:
            pay_button = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Pay ₦1,500 via Paystack", url=pay_url)]]
            )
            await query.edit_message_text(
                "Click the link below to complete your rental payment:\n\nYour"
                " subscription activates automatically upon payment completion.",
                reply_markup=pay_button,
            )
        else:
            await query.edit_message_text(
                "Unable to generate payment link. Please check your API keys."
            )

    elif query.data == "use_tool":
        if is_rental_active(telegram_id):
            expiry_obj = get_rental_expiry(telegram_id)
            expiry_str = (
                expiry_obj.strftime("%d %b, %Y") if expiry_obj else "30 days"
            )

            access_text = (
                f"✅ *Access Granted! Welcome to Nexora VIP.*\n\n"
                f"Your *30-Day Rental Pass* is active! Here is what you get:\n\n"
                f"🔓 *Unrestricted AI Access:* Full access to all Nexora AI features & tools.\n"
                f"⚡ *Priority Processing Speed:* High-priority queue for fast output.\n"
                f"🚫 *No Daily Limits or Cooldowns:* Zero usage caps or timers.\n"
                f"🌟 *VIP Features & Updates:* Instant access to new updates.\n"
                f"🛡️ *30-Day Validity:* Active until {expiry_str}.\n\n"
                f"👇 Tap the button below to launch your workspace and enjoy your access:"
            )

            # WebApp button to open workspace directly in Telegram
            launch_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🚀 Launch AI Workspace", web_app=WebAppInfo(url=f"{WEB_APP_URL}/workspace"))]]
            )

            await query.edit_message_text(
                text=access_text, reply_markup=launch_keyboard, parse_mode="Markdown"
            )
        else:
            renew_button = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Rent Pass — ₦1,500", callback_data="rent")]]
            )
            await query.edit_message_text(
                "❌ *Access Denied*: You do not have an active rental pass.\n\nPlease"
                " subscribe to unlock access.",
                reply_markup=renew_button,
                parse_mode="Markdown",
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
