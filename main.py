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

# LIVE RENDER WEB APP URL
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
    return "Nexora Core API Infrastructure is Operational.", 200


@app.route("/workspace")
def workspace():
    """Enterprise Luxury Gold & Purple UI Dashboard"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
        <title>Nexora Executive Workspace</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-deep: #0b0612;
                --bg-card: rgba(22, 12, 36, 0.7);
                --purple-accent: #6b21a8;
                --purple-light: #a855f7;
                --gold-primary: #d4af37;
                --gold-light: #fef08a;
                --gold-gradient: linear-gradient(135deg, #bf953f 0%, #fcf6ba 25%, #b38728 50%, #fbf5b7 75%, #aa771c 100%);
                --text-main: #f8fafc;
                --text-muted: #94a3b8;
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Plus Jakarta Sans', sans-serif;
                -webkit-tap-highlight-color: transparent;
            }

            body {
                background: var(--bg-deep);
                background-image: 
                    radial-gradient(circle at 10% 10%, rgba(107, 33, 168, 0.25) 0%, transparent 40%),
                    radial-gradient(circle at 90% 90%, rgba(180, 135, 40, 0.15) 0%, transparent 40%);
                color: var(--text-main);
                min-height: 100vh;
                padding: 24px 16px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }

            .brand-header {
                text-align: center;
                margin-bottom: 28px;
                width: 100%;
                max-width: 440px;
            }

            .badge {
                background: rgba(180, 135, 40, 0.12);
                border: 1px solid rgba(212, 175, 55, 0.4);
                color: var(--gold-light);
                padding: 6px 16px;
                font-size: 10px;
                font-weight: 700;
                border-radius: 30px;
                text-transform: uppercase;
                letter-spacing: 2px;
                display: inline-block;
                margin-bottom: 12px;
            }

            h1 {
                font-size: 26px;
                font-weight: 800;
                letter-spacing: -0.5px;
                background: var(--gold-gradient);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 6px;
            }

            p.subtitle {
                font-size: 13px;
                color: var(--text-muted);
                font-weight: 400;
            }

            .container {
                width: 100%;
                max-width: 440px;
                display: flex;
                flex-direction: column;
                gap: 14px;
            }

            .card {
                background: var(--bg-card);
                border: 1px solid rgba(168, 85, 247, 0.2);
                border-radius: 16px;
                padding: 18px;
                backdrop-filter: blur(16px);
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
            }

            .card:hover {
                border-color: rgba(212, 175, 55, 0.5);
                box-shadow: 0 8px 24px -6px rgba(107, 33, 168, 0.4);
                transform: translateY(-2px);
            }

            .card-left {
                display: flex;
                align-items: center;
                gap: 14px;
                flex: 1;
            }

            .icon-wrapper {
                width: 44px;
                height: 44px;
                border-radius: 12px;
                background: linear-gradient(135deg, rgba(107, 33, 168, 0.6), rgba(30, 16, 50, 0.8));
                border: 1px solid rgba(212, 175, 55, 0.3);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
                flex-shrink: 0;
            }

            .card-details {
                display: flex;
                flex-direction: column;
            }

            .card-title {
                font-size: 15px;
                font-weight: 700;
                color: #ffffff;
                margin-bottom: 2px;
            }

            .card-desc {
                font-size: 11px;
                color: var(--text-muted);
                line-height: 1.3;
            }

            .btn-action {
                padding: 10px 18px;
                border: none;
                border-radius: 10px;
                background: var(--gold-gradient);
                color: #0b0612;
                font-size: 12px;
                font-weight: 700;
                text-decoration: none;
                cursor: pointer;
                transition: all 0.2s ease;
                white-space: nowrap;
                box-shadow: 0 4px 12px rgba(180, 135, 40, 0.25);
            }

            .btn-action:active {
                transform: scale(0.96);
            }

            .footer {
                margin-top: 32px;
                font-size: 11px;
                color: #58416d;
                text-align: center;
                font-weight: 500;
            }
        </style>
    </head>
    <body>

        <div class="brand-header">
            <span class="badge">NEXORA PRO ACCESS</span>
            <h1>AI Intelligence Suite</h1>
            <p class="subtitle">Select a verified tool to launch your session</p>
        </div>

        <div class="container">

            <!-- ChatGPT Card -->
            <div class="card">
                <div class="card-left">
                    <div class="icon-wrapper">🤖</div>
                    <div class="card-details">
                        <div class="card-title">ChatGPT / GPT-4o</div>
                        <div class="card-desc">Advanced reasoning & code engine</div>
                    </div>
                </div>
                <a href="https://chatgpt.com" target="_blank" class="btn-action">Launch</a>
            </div>

            <!-- Claude Card -->
            <div class="card">
                <div class="card-left">
                    <div class="icon-wrapper">⚡</div>
                    <div class="card-details">
                        <div class="card-title">Claude 3.5 Sonnet</div>
                        <div class="card-desc">Long-context analysis & writing</div>
                    </div>
                </div>
                <a href="https://claude.ai" target="_blank" class="btn-action">Launch</a>
            </div>

            <!-- Image AI Card -->
            <div class="card">
                <div class="card-left">
                    <div class="icon-wrapper">🎨</div>
                    <div class="card-details">
                        <div class="card-title">Ideogram Studio</div>
                        <div class="card-desc">Professional typography & design</div>
                    </div>
                </div>
                <a href="https://ideogram.ai" target="_blank" class="btn-action">Launch</a>
            </div>

            <!-- Gemini Card -->
            <div class="card">
                <div class="card-left">
                    <div class="icon-wrapper">✨</div>
                    <div class="card-title">Google Gemini Pro</div>
                    <div class="card-desc">Real-time multimodal search</div>
                </div>
                <a href="https://gemini.google.com" target="_blank" class="btn-action">Launch</a>
            </div>

        </div>

        <div class="footer">
            Nexora Technologies • Encrypted Workspace Portal
        </div>

        <script>
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

        activate_rental(telegram_id, reference, days=30)

        expiry_date = (
            datetime.datetime.now() + datetime.timedelta(days=30)
        ).strftime("%d %b, %Y")

        welcome_text = (
            f"👑 *Subscription Activated — Nexora Executive*\n\n"
            f"Your 30-Day All-Access Pass is now active through *{expiry_date}*.\n\n"
            f"✦ *Unlimited Tool Access:* GPT-4o, Claude 3.5, Ideogram & Gemini Pro\n"
            f"✦ *Zero Latency:* Priority high-speed server allocation\n"
            f"✦ *Uncapped Usage:* No cooldown timers or daily caps\n\n"
            f"Tap below to launch your workspace:"
        )

        inline_keyboard = {
            "inline_keyboard": [[
                {"text": "⚡ Launch Workspace", "web_app": {"url": f"{WEB_APP_URL}/workspace"}}
            ]]
        }

        send_telegram_message(telegram_id, welcome_text, reply_markup=inline_keyboard)
        return jsonify({"status": "success"}), 200

    return jsonify({"status": "ignored"}), 200


def run_flask():
    app.run(host="0.0.0.0", port=PORT)


# ------------------- TELEGRAM BOT HANDLERS -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if is_rental_active(telegram_id):
        expiry_obj = get_rental_expiry(telegram_id)
        expiry_str = expiry_obj.strftime("%d %b, %Y") if expiry_obj else "Active"
        
        text = (
            f"👑 *Nexora Executive Portal*\n\n"
            f"Status: *Active VIP Pass* (Valid until {expiry_str})\n"
            f"Access your suite of premium AI engines directly inside Telegram below:"
        )
        keyboard = [
            [InlineKeyboardButton("⚡ Open AI Workspace", web_app=WebAppInfo(url=f"{WEB_APP_URL}/workspace"))],
            [InlineKeyboardButton("💳 Subscription Details", callback_data="rent")]
        ]
    else:
        text = (
            f"🏛 *Welcome to Nexora AI Studio*\n\n"
            f"Gain instant access to top-tier AI platforms (ChatGPT-4o, Claude 3.5, Ideogram, Gemini Pro) under one unified workspace.\n\n"
            f"• *Plan:* 30-Day Executive Pass\n"
            f"• *Price:* ₦1,500 / month\n"
            f"• *Activation:* Automatic instant delivery"
        )
        keyboard = [
            [InlineKeyboardButton("👑 Unlock 30-Day Pass (₦1,500)", callback_data="rent")],
            [InlineKeyboardButton("⚡ Preview AI Workspace", web_app=WebAppInfo(url=f"{WEB_APP_URL}/workspace"))]
        ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
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
            pay_button = InlineKeyboardMarkup(
                [[InlineKeyboardButton("💳 Complete Payment via Paystack", url=pay_url)]]
            )
            await query.edit_message_text(
                "*Nexora Executive Checkout*\n\nClick below to activate your 30-day subscription. Activation takes less than 5 seconds after payment confirmation.",
                reply_markup=pay_button,
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "Unable to generate checkout link. Please try again shortly."
            )


# ------------------- MAIN ENTRY POINT -------------------
if __name__ == "__main__":
    init_db()

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(handle_button))

    print("Nexora Bot Engine Online...")
    telegram_app.run_polling()
