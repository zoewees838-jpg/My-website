import os
import sqlite3
import random
import string
import threading
from flask import Flask, render_template_string, request, jsonify
import telebot
from telebot import types

# ---------------------------------------------------------
# ENVIRONMENT & BOT CONFIGURATION
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://my-website-nwa5.onrender.com").rstrip("/")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

DB_NAME = "apex_nexora.db"

# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.00,
            account_status TEXT DEFAULT 'PENDING'
        )
    """)
    
    # Deposit Requests Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deposit_requests (
            deposit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL DEFAULT 100.00,
            status TEXT DEFAULT 'PENDING_APPROVAL',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Bets Table with strict Bet Access Codes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bet_code TEXT UNIQUE,
            match_name TEXT,
            selection TEXT,
            odds REAL,
            stake REAL,
            potential_payout REAL,
            status TEXT DEFAULT 'PENDING'
        )
    """)
    conn.commit()
    conn.close()

init_db()

def generate_bet_code():
    chars = string.ascii_uppercase + string.digits
    return "NEX-" + "".join(random.choices(chars, k=6))

def get_or_create_user(user_id, username="Bettor"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, username, balance, account_status) VALUES (?, ?, 0.00, 'PENDING')",
            (user_id, username)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

# ---------------------------------------------------------
# MINI APP FRONTEND HTML (PINK & GREEN THEME)
# ---------------------------------------------------------
WEBAPP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexora VIP Manager Terminal</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg-color: #0d0e12;
            --card-bg: #161820;
            --pink-accent: #ff2a85;
            --pink-glow: rgba(255, 42, 133, 0.3);
            --green-accent: #00ff87;
            --green-glow: rgba(0, 255, 135, 0.3);
            --text-main: #ffffff;
            --text-muted: #8a8f9d;
            --border-color: #262936;
        }

        body {
            margin: 0;
            padding: 16px;
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }

        .header-card {
            background: linear-gradient(135deg, #1f1124 0%, #0d1e18 100%);
            border: 1px solid var(--pink-accent);
            box-shadow: 0 0 15px var(--pink-glow);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
            text-align: center;
        }

        .header-title {
            color: var(--pink-accent);
            font-size: 18px;
            font-weight: 800;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin: 0 0 6px 0;
        }

        .balance-box {
            font-size: 28px;
            font-weight: 700;
            color: var(--green-accent);
            text-shadow: 0 0 10px var(--green-glow);
            margin: 10px 0;
        }

        .badge-status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            background-color: #ff2a8522;
            color: var(--pink-accent);
            border: 1px solid var(--pink-accent);
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 15px;
        }

        .input-group { margin-bottom: 12px; }
        .input-group label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }

        .input-field {
            width: 100%;
            padding: 12px;
            background: #0d0e12;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--green-accent);
            font-family: monospace;
            font-size: 16px;
            box-sizing: border-box;
        }

        .btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 14px;
            letter-spacing: 1px;
            text-transform: uppercase;
            cursor: pointer;
        }

        .btn-pink { background: var(--pink-accent); color: #ffffff; box-shadow: 0 0 12px var(--pink-glow); }
        .btn-green { background: var(--green-accent); color: #0d0e12; box-shadow: 0 0 12px var(--green-glow); }

        .odds-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px; }
        .odds-btn {
            background: #0d0e12;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 4px;
            color: var(--text-main);
            text-align: center;
            font-size: 12px;
            cursor: pointer;
        }
        .odds-btn span { display: block; color: var(--green-accent); font-weight: bold; font-size: 14px; margin-top: 4px; }
        .odds-btn.selected { border-color: var(--pink-accent); background: #ff2a8515; }
    </style>
</head>
<body>
    <div class="header-card">
        <div class="header-title">Nexora VIP Terminal</div>
        <div class="balance-box">₦<span id="user-balance">0.00</span></div>
        <div id="account-status" class="badge-status">DEPOSIT REQUIRED</div>
    </div>

    <div class="card">
        <div class="input-group">
            <label>ENTER BET ACCESS CODE</label>
            <input type="text" id="bet-code-input" class="input-field" placeholder="e.g. NEX-AB1234">
        </div>
        <button id="verify-code-btn" class="btn btn-pink" onclick="verifyCode()">Verify Access Code</button>
    </div>

    <div id="betting-section" class="card" style="display: none;">
        <div style="font-size: 14px; font-weight: bold; color: var(--pink-accent);">⚽ Real Madrid vs Man United</div>
        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 10px;">Format: 2x (30 Mins + 3 Mins Stoppage)</div>
        
        <div class="odds-grid">
            <div class="odds-btn" onclick="selectMarket('1', 2.10, this)">RM (1)<span>2.10</span></div>
            <div class="odds-btn" onclick="selectMarket('X', 3.40, this)">Draw (X)<span>3.40</span></div>
            <div class="odds-btn" onclick="selectMarket('2', 3.25, this)">MU (2)<span>3.25</span></div>
        </div>

        <div style="margin-top: 15px;">
            <label style="font-size: 11px; color: var(--text-muted);">FIXED STAKE AMOUNT</label>
            <input type="text" class="input-field" value="₦100.00" disabled style="margin-top: 4px;">
        </div>

        <button id="place-bet-btn" class="btn btn-green" style="margin-top: 15px;" onclick="placeBet()" disabled>Confirm Wager</button>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        let selectedMarket = null;
        let selectedOdds = 0;
        let activeBetCode = '';
        const userId = tg.initDataUnsafe?.user?.id || 0;

        async function fetchUserData() {
            if (!userId) return;
            try {
                const res = await fetch(`/api/user/${userId}`);
                const data = await res.json();
                document.getElementById('user-balance').innerText = data.balance.toFixed(2);
                document.getElementById('account-status').innerText = data.account_status;
            } catch (e) { console.error(e); }
        }

        async function verifyCode() {
            const code = document.getElementById('bet-code-input').value.trim();
            if (!code) { tg.showAlert('Please enter your Bet Access Code.'); return; }

            const res = await fetch('/api/verify-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: userId, code: code })
            });

            const data = await res.json();
            if (data.success) {
                activeBetCode = code;
                document.getElementById('betting-section').style.display = 'block';
                document.getElementById('bet-code-input').disabled = true;
                document.getElementById('verify-code-btn').disabled = true;
                tg.showAlert('Access Code Verified!');
            } else {
                tg.showAlert(data.message || 'Invalid or used Access Code.');
            }
        }

        function selectMarket(market, odds, el) {
            document.querySelectorAll('.odds-btn').forEach(b => b.classList.remove('selected'));
            el.classList.add('selected');
            selectedMarket = market;
            selectedOdds = odds;
            document.getElementById('place-bet-btn').disabled = false;
        }

        async function placeBet() {
            if (!selectedMarket || !activeBetCode) return;

            const res = await fetch('/api/place-bet', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    user_id: userId,
                    code: activeBetCode,
                    selection: selectedMarket,
                    odds: selectedOdds,
                    stake: 100.0
                })
            });

            const data = await res.json();
            if (data.success) {
                tg.showAlert('Bet Placed Successfully!');
                location.reload();
            } else {
                tg.showAlert(data.message || 'Failed to place bet.');
            }
        }

        fetchUserData();
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# FLASK WEB APP ROUTES
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template_string(WEBAPP_HTML)

@app.route('/api/user/<int:user_id>')
def api_get_user(user_id):
    user = get_or_create_user(user_id)
    return jsonify({
        "user_id": user["user_id"],
        "balance": user["balance"],
        "account_status": user["account_status"]
    })

@app.route('/api/verify-code', methods=['POST'])
def api_verify_code():
    data = request.json
    user_id = data.get('user_id')
    code = data.get('code', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bets WHERE bet_code = ? AND user_id = ? AND status = 'PENDING'", (code, user_id))
    bet = cursor.fetchone()
    conn.close()

    if bet:
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid code or bet already placed."})

@app.route('/api/place-bet', methods=['POST'])
def api_place_bet():
    data = request.json
    user_id = data.get('user_id')
    code = data.get('code')
    selection = data.get('selection')
    odds = data.get('odds')
    stake = float(data.get('stake', 100.0))

    user = get_or_create_user(user_id)

    if user["balance"] < stake:
        return jsonify({"success": False, "message": "Insufficient balance. Deposit ₦100 to continue."})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (stake, user_id))
    cursor.execute("""
        UPDATE bets 
        SET selection = ?, odds = ?, stake = ?, potential_payout = ?, status = 'PLACED'
        WHERE bet_code = ? AND user_id = ?
    """, (selection, odds, stake, stake * odds, code, user_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

# ---------------------------------------------------------
# TELEGRAM BOT HANDLERS
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.first_name)

    markup = types.InlineKeyboardMarkup(row_width=1)
    webapp_info = types.WebAppInfo(url=WEBAPP_URL)
    
    btn_launch = types.InlineKeyboardButton("🚀 Launch Nexora VIP Manager", webapp=webapp_info)
    btn_deposit = types.InlineKeyboardButton("💳 Request Deposit (₦100)", callback_data="req_deposit")
    btn_generate_code = types.InlineKeyboardButton("🔑 Generate Bet Access Code", callback_data="gen_code")
    
    markup.add(btn_launch, btn_deposit, btn_generate_code)

    welcome_text = (
        f"👑 <b>NEXORA VIP TERMINAL</b>\n"
        f"-----------------------------------------\n"
        f"👤 <b>Bettor:</b> {user['username']}\n"
        f"💰 <b>Balance:</b> ₦{user['balance']:,.2f}\n"
        f"🛡️ <b>Status:</b> <code>{user['account_status']}</code>\n"
        f"-----------------------------------------\n"
        f"<i>Tap below to launch the VIP Manager Mini App or request funding.</i>"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.first_name)

    if call.data == "req_deposit":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO deposit_requests (user_id, amount) VALUES (?, 100.00)", (user_id,))
        dep_id = cursor.lastrowid
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, "Deposit request for ₦100 submitted to Admin.", show_alert=True)

        if ADMIN_ID:
            admin_markup = types.InlineKeyboardMarkup(row_width=2)
            b_approve = types.InlineKeyboardButton("✅ Approve ₦100", callback_data=f"adm_approve_{dep_id}_{user_id}")
            b_reject = types.InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject_{dep_id}_{user_id}")
            admin_markup.add(b_approve, b_reject)

            bot.send_message(
                ADMIN_ID,
                f"📥 <b>NEW DEPOSIT REQUEST #{dep_id}</b>\n\n"
                f"👤 <b>User:</b> {user['username']} (<code>{user_id}</code>)\n"
                f"💵 <b>Amount:</b> ₦100.00\n\n"
                f"Confirm physical/cash deposit before approval:",
                reply_markup=admin_markup
            )

    elif call.data == "gen_code":
        code = generate_bet_code()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO bets (user_id, bet_code, match_name, status) VALUES (?, ?, 'Real Madrid vs Man United', 'PENDING')",
            (user_id, code)
        )
        conn.commit()
        conn.close()

        msg = (
            f"🔑 <b>BET ACCESS CODE GENERATED</b>\n"
            f"-----------------------------------------\n"
            f"Code: <code>{code}</code>\n"
            f"-----------------------------------------\n"
            f"<i>Copy this code and paste it inside the Nexora VIP Mini App to unlock bet placement.</i>"
        )
        bot.send_message(call.message.chat.id, msg)

    elif call.data.startswith("adm_approve_"):
        _, _, dep_id, target_user_id = call.data.split("_")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE deposit_requests SET status = 'APPROVED' WHERE deposit_id = ?", (dep_id,))
        cursor.execute("UPDATE users SET balance = balance + 100.00, account_status = 'ACTIVE' WHERE user_id = ?", (target_user_id,))
        conn.commit()
        conn.close()

        bot.edit_message_text(f"✅ Approved Deposit #{dep_id} for User {target_user_id}.", call.message.chat.id, call.message.message_id)
        bot.send_message(target_user_id, "🎉 <b>DEPOSIT CONFIRMED</b>\n\nYour ₦100.00 deposit has been confirmed by Admin. Your balance is updated!")

    elif call.data.startswith("adm_reject_"):
        _, _, dep_id, target_user_id = call.data.split("_")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE deposit_requests SET status = 'REJECTED' WHERE deposit_id = ?", (dep_id,))
        conn.commit()
        conn.close()

        bot.edit_message_text(f"❌ Rejected Deposit #{dep_id}.", call.message.chat.id, call.message.message_id)
        bot.send_message(target_user_id, "❌ <b>DEPOSIT REJECTED</b>\n\nYour deposit request was not confirmed. Contact Admin.")

@bot.message_handler(commands=['settle'])
def cmd_settle(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    try:
        _, code, outcome = message.text.split()
        outcome = outcome.lower()
    except ValueError:
        bot.reply_to(message, "Usage: <code>/settle <bet_code> <win|loss></code>")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bets WHERE bet_code = ?", (code,))
    bet = cursor.fetchone()

    if not bet:
        bot.reply_to(message, "Bet code not found.")
        conn.close()
        return

    target_user_id = bet["user_id"]

    if outcome == "win":
        payout = bet["potential_payout"]
        cursor.execute("UPDATE bets SET status = 'WON' WHERE bet_code = ?", (code,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, target_user_id))
        conn.commit()

        msg = (
            f"🏆 <b>BET SLIP RESULT: WON</b>\n"
            f"-----------------------------------------\n"
            f"🎟️ <b>Slip Code:</b> <code>{code}</code>\n"
            f"💵 <b>Payout:</b> ₦{payout:,.2f}\n"
            f"-----------------------------------------\n"
            f"📞 <b>Important:</b> Please contact your local manager to process your withdrawal payout."
        )
        bot.send_message(target_user_id, msg)
        bot.reply_to(message, f"Bet {code} marked as WON. User notified.")

    elif outcome == "loss":
        cursor.execute("UPDATE bets SET status = 'LOST' WHERE bet_code = ?", (code,))
        conn.commit()

        msg = (
            f"📉 <b>BET SLIP RESULT: LOST</b>\n"
            f"-----------------------------------------\n"
            f"🎟️ <b>Slip Code:</b> <code>{code}</code>\n"
            f"-----------------------------------------\n"
            f"📞 <b>Notice:</b> Please contact your local manager for slip reconciliation and match analysis."
        )
        bot.send_message(target_user_id, msg)
        bot.reply_to(message, f"Bet {code} marked as LOST. User notified.")

    conn.close()

# ---------------------------------------------------------
# SERVER STARTUP (RESOLVES PORT CONFLICTS ON RENDER)
# ---------------------------------------------------------
def run_bot():
    print("⚡ Nexora Telegram Bot Starting...")
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    # Start Telegram polling thread in background
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Run Flask server on Render's provided environment PORT
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
