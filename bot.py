import os
import sqlite3
import random
import string
import threading
import time
import requests
from flask import Flask, render_template_string, request, jsonify
import telebot
from telebot import types

# ---------------------------------------------------------
# CONFIGURATION & ENVIRONMENT SETUP
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    # Fallback to provided token if environment variable is not explicitly injected
    BOT_TOKEN = "8706915052:AAEfBy3Kh7BNi2FiyHwaPvhzgqX4L8uP9Nw"

ADMIN_ID = os.getenv("ADMIN_ID", "0")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://my-website-nwa5.onrender.com").rstrip("/")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

DB_NAME = "apex_nexora.db"

# ---------------------------------------------------------
# DATABASE SETUP (THREAD-SAFE CONNECTIONS)
# ---------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
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
            first_name TEXT,
            balance REAL DEFAULT 0.00,
            vip_tier TEXT DEFAULT 'BRONZE',
            account_status TEXT DEFAULT 'ACTIVE',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Deposits table
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
    
    # Access/Bet Codes table
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
# FULL MINI APP UI (DARK TECH PINK & GREEN THEME)
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
            --pink-accent: #ff2a85;
            --green-accent: #00ff87;
            --text-main: #ffffff;
            --text-muted: #8a8f9d;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            padding: 16px;
            margin: 0;
            padding-bottom: 80px;
        }
        .header-card {
            border: 1px solid var(--pink-accent);
            background: linear-gradient(135deg, #1f1124 0%, #151821 100%);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(255, 42, 133, 0.15);
        }
        .title {
            color: var(--pink-accent);
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
            text-shadow: 0 0 10px rgba(0, 255, 135, 0.2);
        }
        .badge {
            display: inline-block;
            background: rgba(255, 42, 133, 0.2);
            color: var(--pink-accent);
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
            color: var(--text-main);
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
            transition: transform 0.1s ease;
        }
        .btn:active { transform: scale(0.98); }
        .btn-pink { background: var(--pink-accent); color: #fff; }
        .btn-green { background: var(--green-accent); color: #000; }
        
        .code-card {
            background: var(--card-bg);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 16px;
            margin-top: 12px;
        }
        .nav-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #12141c;
            border-top: 1px solid rgba(255,255,255,0.08);
            display: flex;
            justify-content: space-around;
            padding: 12px 0;
        }
        .nav-item {
            color: var(--text-muted);
            font-size: 11px;
            text-align: center;
            text-decoration: none;
        }
        .nav-item.active { color: var(--pink-accent); font-weight: bold; }
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
        <button class="btn btn-pink" onclick="requestDeposit()">+ Deposit</button>
        <button class="btn btn-green" onclick="generateCode()">Get Code</button>
    </div>

    <div class="section-title">Active VIP Access Codes</div>
    <div id="code-list">
        <div class="code-card" style="color: var(--text-muted); text-align: center;">
            No active access codes generated yet.
        </div>
    </div>

    <div class="nav-bar">
        <div class="nav-item active">🏠 Home</div>
        <div class="nav-item" onclick="tg.close()">❌ Exit</div>
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
                list.innerHTML = 
