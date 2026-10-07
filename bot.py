import os
import sqlite3
import random
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# ---------------------------------------------------------
# ENVIRONMENT & BOT INITIALIZATION
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ---------------------------------------------------------
# DUMMY HTTP SERVER FOR RENDER PORT BINDING
# ---------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Apex Bet Sportsbook Engine Running")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return  # Suppress stdout web logging

def run_http_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------
DB_NAME = "apex_bet.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 5000.00
        )
    """)
    
    # Bets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
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

# Database Helper Functions
def get_user(user_id, username="User"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)", (user_id, username, 5000.00))
        conn.commit()
        user = (user_id, username, 5000.00)
    conn.close()
    return user

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def place_bet_db(user_id, match_name, selection, odds, stake):
    potential = stake * odds
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (stake, user_id))
    cursor.execute("""
        INSERT INTO bets (user_id, match_name, selection, odds, stake, potential_payout)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, match_name, selection, odds, stake, potential))
    bet_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return bet_id, potential

def get_user_bets(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT bet_id, match_name, selection, odds, stake, potential_payout, status FROM bets WHERE user_id = ? ORDER BY bet_id DESC LIMIT 5", (user_id,))
    bets = cursor.fetchall()
    conn.close()
    return bets

# ---------------------------------------------------------
# FIXTURE & ODDS CALCULATION
# ---------------------------------------------------------
# Real Madrid vs Manchester United
# Match scheduled for 5:00 PM (17:00 local time)
MATCH_DETAILS = {
    "home": "Real Madrid",
    "away": "Manchester United",
    "kickoff": "Today / Tomorrow @ 5:00 PM",
    "time_str": "17:00",
    "format": "2x (30 Mins + 3 Mins Stoppage)",
    "odds": {
        "1": 2.10,      # Real Madrid Win
        "X": 3.40,      # Draw
        "2": 3.25,      # Manchester United Win
        "O2.5": 1.85,   # Over 2.5 Goals
        "U2.5": 1.95,   # Under 2.5 Goals
        "BTTS_Y": 1.70, # Both Teams To Score - Yes
        "BTTS_N": 2.10  # Both Teams To Score - No
    }
}

# ---------------------------------------------------------
# UI KEYBOARDS & UI BUILDERS
# ---------------------------------------------------------
def main_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("🏆 Featured Fixtures", callback_data="view_fixtures")
    b2 = types.InlineKeyboardButton("💳 VIP Wallet", callback_data="view_wallet")
    b3 = types.InlineKeyboardButton("📜 Active Slips", callback_data="view_slips")
    b4 = types.InlineKeyboardButton("⏱️ Live Match Schedule", callback_data="view_clock")
    markup.add(b1, b2)
    markup.add(b3, b4)
    return markup

def match_odds_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=3)
    o = MATCH_DETAILS["odds"]
    
    # 1X2 Market
    b_home = types.InlineKeyboardButton(f"1 (RM): {o['1']}", callback_data="bet_1")
    b_draw = types.InlineKeyboardButton(f"X (Draw): {o['X']}", callback_data="bet_X")
    b_away = types.InlineKeyboardButton(f"2 (MU): {o['2']}", callback_data="bet_2")
    
    # Goals Market
    b_o25 = types.InlineKeyboardButton(f"Over 2.5: {o['O2.5']}", callback_data="bet_O2.5")
    b_u25 = types.InlineKeyboardButton(f"Under 2.5: {o['U2.5']}", callback_data="bet_U2.5")
    
    # BTTS
    b_btts_y = types.InlineKeyboardButton(f"BTTS Yes: {o['BTTS_Y']}", callback_data="bet_BTTS_Y")
    b_btts_n = types.InlineKeyboardButton(f"BTTS No: {o['BTTS_N']}", callback_data="bet_BTTS_N")
    
    b_back = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
    
    markup.add(b_home, b_draw, b_away)
    markup.add(b_o25, b_u25)
    markup.add(b_btts_y, b_btts_n)
    markup.add(b_back)
    return markup

# ---------------------------------------------------------
# BOT HANDLERS
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    welcome_text = (
        f"👑 <b>APEX BET VIP SPORTSBOOK</b>\n"
        f"<i>Premium Automated Betting Terminal</i>\n\n"
        f"👤 <b>Bettor:</b> {user[1]}\n"
        f"💰 <b>Wallet Balance:</b> ₦{user[2]:,.2f}\n"
        f"⚡ <b>System Status:</b> Operational\n\n"
        f"Select an option below to view live odds or manage your account:"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    user = get_user(user_id, call.from_user.first_name)

    if call.data == "main_menu":
        text = (
            f"👑 <b>APEX BET VIP SPORTSBOOK</b>\n\n"
            f"👤 <b>Account:</b> {user[1]}\n"
            f"💰 <b>Balance:</b> ₦{user[2]:,.2f}\n\n"
            f"Select an option to proceed:"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu_keyboard())

    elif call.data == "view_fixtures":
        m = MATCH_DETAILS
        text = (
            f"⚽ <b>UPCOMING FEATURED FIXTURE</b>\n"
            f"-----------------------------------------\n"
            f"🔥 <b>{m['home']} vs {m['away']}</b>\n"
            f"⏰ <b>Kickoff Time:</b> 5:00 PM Sharp\n"
            f"⏱️ <b>Format:</b> {m['format']}\n"
            f"-----------------------------------------\n"
            f"<b>Match Odds (1X2 & Markets):</b>\n"
            f"• Real Madrid (1): <code>{m['odds']['1']}</code>\n"
            f"• Draw (X): <code>{m['odds']['X']}</code>\n"
            f"• Man United (2): <code>{m['odds']['2']}</code>\n"
            f"• Over 2.5 Goals: <code>{m['odds']['O2.5']}</code>\n"
            f"• Both Teams To Score: <code>{m['odds']['BTTS_Y']}</code>\n\n"
            f"<i>Tap a market below to select your wager:</i>"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=match_odds_keyboard())

    elif call.data.startswith("bet_"):
        selection_key = call.data.replace("bet_", "")
        odds = MATCH_DETAILS["odds"].get(selection_key, 2.00)
        
        # Standard default stake for quick placement
        stake = 1000.00
        
        if user[2] < stake:
            bot.answer_callback_query(call.id, "❌ Insufficient balance! Please deposit funds.", show_alert=True)
            return

        match_name = f"{MATCH_DETAILS['home']} vs {MATCH_DETAILS['away']}"
        bet_id, potential = place_bet_db(user_id, match_name, selection_key, odds, stake)
        
        updated_user = get_user(user_id)
        
        text = (
            f"✅ <b>BET SLIP CONFIRMED #APX-{bet_id}</b>\n"
            f"-----------------------------------------\n"
            f"⚽ <b>Match:</b> {match_name}\n"
            f"⏰ <b>Kickoff:</b> 5:00 PM\n"
            f"🎯 <b>Selection:</b> {selection_key}\n"
            f"📊 <b>Odds:</b> {odds}\n"
            f"💵 <b>Stake:</b> ₦{stake:,.2f}\n"
            f"🏆 <b>Potential Win:</b> ₦{potential:,.2f}\n"
            f"-----------------------------------------\n"
            f"💳 <b>Remaining Balance:</b> ₦{updated_user[2]:,.2f}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Fixtures", callback_data="view_fixtures"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "view_wallet":
        text = (
            f"💳 <b>VIP WALLET OVERVIEW</b>\n"
            f"-----------------------------------------\n"
            f"👤 <b>Account Holder:</b> {user[1]}\n"
            f"🆔 <b>User ID:</b> <code>{user[0]}</code>\n"
            f"💵 <b>Available Balance:</b> ₦{user[2]:,.2f}\n"
            f"-----------------------------------------\n"
            f"<i>Use the quick action buttons below:</i>"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        b_dep = types.InlineKeyboardButton("➕ Quick Deposit (₦5,000)", callback_data="quick_deposit")
        b_back = types.InlineKeyboardButton("🔙 Back", callback_data="main_menu")
        markup.add(b_dep)
        markup.add(b_back)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "quick_deposit":
        update_balance(user_id, 5000.00)
        updated_user = get_user(user_id)
        bot.answer_callback_query(call.id, "🎉 ₦5,000.00 successfully added to your balance!", show_alert=True)
        
        text = (
            f"💳 <b>VIP WALLET OVERVIEW</b>\n"
            f"-----------------------------------------\n"
            f"👤 <b>Account Holder:</b> {updated_user[1]}\n"
            f"💵 <b>Updated Balance:</b> ₦{updated_user[2]:,.2f}\n"
            f"-----------------------------------------"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "view_slips":
        bets = get_user_bets(user_id)
        if not bets:
            text = "📜 <b>ACTIVE SLIPS</b>\n\nYou currently have no active bet slips placed."
        else:
            text = "📜 <b>YOUR RECENT BET SLIPS</b>\n-----------------------------------------\n"
            for b in bets:
                text += (
                    f"🎟️ <b>Slip #APX-{b[0]}</b> | Status: <b>{b[6]}</b>\n"
                    f"⚽ {b[1]}\n"
                    f"🎯 Pick: {b[2]} @ {b[3]} | Stake: ₦{b[4]:,.2f}\n"
                    f"🏆 Return: ₦{b[5]:,.2f}\n"
                    f"-----------------------------------------\n"
                )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "view_clock":
        text = (
            f"⏱️ <b>MATCH TIMELINE & SCHEDULE</b>\n"
            f"-----------------------------------------\n"
            f"⚽ <b>Fixture:</b> Real Madrid vs Manchester United\n"
            f"⏰ <b>Kickoff Time:</b> 5:00 PM Sharp\n\n"
            f"📌 <b>Timeline breakdown:</b>\n"
            f"• <b>5:00 PM:</b> First Half Kickoff (30m + 3m stoppage)\n"
            f"• <b>5:33 PM:</b> Half Time Break (10 mins rest)\n"
            f"• <b>5:43 PM:</b> Second Half Kickoff (30m + 3m stoppage)\n"
            f"• <b>6:16 PM:</b> Full Time Whistle (66 Total Mins)\n"
            f"-----------------------------------------\n"
            f"<i>Betting markets close automatically at 5:00 PM.</i>"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ---------------------------------------------------------
# BOT STARTUP
# ---------------------------------------------------------
if __name__ == "__main__":
    print("⚡ Apex Bet VIP Bot Running...")
    bot.infinity_polling()
