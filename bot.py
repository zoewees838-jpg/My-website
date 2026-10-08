import os
import sqlite3
import random
import string
import requests
from flask import Flask, render_template_string, request, jsonify
import telebot
from telebot import types

# ---------------------------------------------------------
# CONFIGURATION & ENVIRONMENT SETUP
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8781475029:AAHfj7KezIayBSJKOO1GkUkMdeC6BWeeF-8").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "0")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://my-website-nwa5.onrender.com").rstrip("/")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

DB_NAME = "apex_nexora.db"

# Webhook configuration
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBAPP_URL}{WEBHOOK_PATH}"

# ---------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0.00,
            vip_tier TEXT DEFAULT 'BRONZE',
            account_status TEXT DEFAULT 'ACTIVE',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deposit_requests (
            deposit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            payment_method TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bet_codes (
            code_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            code TEXT UNIQUE,
            odds REAL,
            stake REAL,
            potential_payout REAL,
            status TEXT DEFAULT 'PENDING',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def generate_bet_code():
    chars = string.ascii_uppercase + string.digits
    return "NEX-" + "".join(random.choices(chars, k=6))

def get_or_create_user(user_id, username="", first_name="Bettor"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, balance, vip_tier, account_status) VALUES (?, ?, ?, 0.00, 'BRONZE', 'ACTIVE')",
            (user_id, username, first_name)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

# ---------------------------------------------------------
# MINI APP UI (DARK TECH CRIMSON & GREEN)
# ---------------------------------------------------------
WEBAPP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexora VIP Manager</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg-color: #0b0c10;
            --card-bg: #151821;
            --red-accent: #dc2626;
            --green-accent: #10b981;
            --text-main: #ffffff;
            --text-muted: #9ca3af;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 16px;
            margin: 0;
            padding-bottom: 80px;
        }
        .header-card {
            border: 1px solid var(--red-accent);
            background: linear-gradient(135deg, #1f1118 0%, #151821 100%);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(220, 38, 38, 0.2);
        }
        .title {
            color: var(--red-accent);
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 1.5px;
            margin: 0 0 8px 0;
        }
        .balance-val {
            font-size: 32px;
            color: var(--green-accent);
            font-weight: 800;
            margin: 4px 0;
        }
        .badge {
            display: inline-block;
            background: rgba(220, 38, 38, 0.2);
            color: var(--red-accent);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 6px;
        }
        .section-title {
            font-size: 16px;
            font-weight: 700;
            margin: 24px 0 12px 0;
        }
        .action-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .btn {
            padding: 14px;
            border: none;
            border-radius: 12px;
            font-weight: 700;
            font-size: 14px;
            cursor: pointer;
        }
        .btn-red { background: var(--red-accent); color: #fff; }
        .btn-green { background: var(--green-accent); color: #fff; }
        .code-card {
            background: var(--card-bg);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 16px;
            margin-top: 12px;
        }
    </style>
</head>
<body>
    <div class="header-card">
        <p class="title">NEXORA VIP TERMINAL</p>
        <div class="balance-val">₦<span id="bal">0.00</span></div>
        <div class="badge" id="status-badge">ACCOUNT: ACTIVE</div>
    </div>

    <div class="section-title">Quick Actions</div>
    <div class="action-grid">
        <button class="btn btn-red" onclick="requestDeposit()">+ Deposit</button>
        <button class="btn btn-green" onclick="generateCode()">Get Code</button>
    </div>

    <div class="section-title">Active VIP Access Codes</div>
    <div id="code-list">
        <div class="code-card" style="color: var(--text-muted); text-align: center;">
            No active access codes generated yet.
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        const userId = tg.initDataUnsafe?.user?.id || 0;

        function loadUserData() {
            if(!userId) return;
            fetch(`/api/user/${userId}`)
                .then(r => r.json())
                .then(d => {
                    document.getElementById('bal').innerText = Number(d.balance).toLocaleString('en-US', {minimumFractionDigits: 2});
                    document.getElementById('status-badge').innerText = `STATUS: ${d.account_status}`;
                })
                .catch(e => console.error(e));
        }

        function requestDeposit() {
            tg.showPopup({
                title: 'Deposit Funds',
                message: 'Submit deposit request for ₦100 to VIP Manager?',
                buttons: [{type: 'ok', id: 'ok'}, {type: 'cancel'}]
            }, function(btnId) {
                if (btnId === 'ok') {
                    fetch('/api/deposit', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({user_id: userId, amount: 100})
                    }).then(() => {
                        tg.showAlert('Deposit request sent to admin!');
                    });
                }
            });
        }

        function generateCode() {
            fetch('/api/generate-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: userId})
            })
            .then(r => r.json())
            .then(d => {
                const list = document.getElementById('code-list');
                list.innerHTML = `
                    <div class="code-card">
                        <div style="color:var(--green-accent); font-weight:bold; font-size:18px;">${d.code}</div>
                        <div style="color:var(--text-muted); font-size:12px; margin-top:4px;">Odds: 2.50 | Status: PENDING</div>
                    </div>
                ` + list.innerHTML;
            });
        }

        loadUserData();
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# FLASK ROUTES & WEBHOOK RECEIVER
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template_string(WEBAPP_HTML)

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

@app.route('/set_webhook')
def set_webhook_route():
    bot.remove_webhook()
    success = bot.set_webhook(url=WEBHOOK_URL)
    if success:
        return f"Webhook set successfully to {WEBHOOK_URL}", 200
    return "Failed to set webhook", 500

@app.route('/api/user/<int:user_id>')
def api_get_user(user_id):
    user = get_or_create_user(user_id)
    return jsonify({
        "balance": user["balance"],
        "account_status": user["account_status"],
        "vip_tier": user["vip_tier"]
    })

@app.route('/api/deposit', methods=['POST'])
def api_deposit():
    data = request.json or {}
    user_id = data.get('user_id')
    amount = data.get('amount', 100.0)
    
    if user_id:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO deposit_requests (user_id, amount, payment_method) VALUES (?, ?, 'MINI_APP')",
            (user_id, amount)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/api/generate-code', methods=['POST'])
def api_gen_code():
    data = request.json or {}
    user_id = data.get('user_id')
    if user_id:
        code = generate_bet_code()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO bet_codes (user_id, code, odds, stake, potential_payout) VALUES (?, ?, 2.50, 100.00, 250.00)",
            (user_id, code)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "code": code})
    return jsonify({"success": False}), 400

# ---------------------------------------------------------
# TELEGRAM BOT HANDLERS
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Bettor"
    
    user = get_or_create_user(user_id, username, first_name)

    markup = types.InlineKeyboardMarkup(row_width=1)
    webapp_info = types.WebAppInfo(url=WEBAPP_URL)
    markup.add(
        types.InlineKeyboardButton("🚀 Launch Nexora VIP Manager", webapp=webapp_info),
        types.InlineKeyboardButton("💳 Request Deposit (₦100)", callback_data="req_deposit"),
        types.InlineKeyboardButton("🔑 Generate Access Code", callback_data="gen_code")
    )

    text = (
        f"👑 <b>NEXORA VIP TERMINAL</b>\n"
        f"-----------------------------------------\n"
        f"👤 <b>Bettor:</b> {user['first_name']}\n"
        f"💰 <b>Balance:</b> ₦{user['balance']:,.2f}\n"
        f"🏆 <b>VIP Tier:</b> {user['vip_tier']}\n"
        f"🛡️ <b>Status:</b> <code>{user['account_status']}</code>\n"
        f"-----------------------------------------\n"
        f"<i>Tap below to open the Mini App or manage your terminal.</i>"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    if call.data == "req_deposit":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO deposit_requests (user_id, amount, payment_method) VALUES (?, 100.0, 'BOT_INLINE')",
            (user_id,)
        )
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "₦100 Deposit Request submitted to Admin!", show_alert=True)
        
    elif call.data == "gen_code":
        code = generate_bet_code()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO bet_codes (user_id, code, odds, stake, potential_payout) VALUES (?, ?, 2.50, 100.00, 250.00)",
            (user_id, code)
        )
        conn.commit()
        conn.close()
        bot.send_message(call.message.chat.id, f"🔑 VIP Access Code: <code>{code}</code>\nOdds: 2.50 | Potential Payout: ₦250.00")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
