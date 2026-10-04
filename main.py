import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Retrieve token from environment variables (configured on Render)
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    welcome_text = (
        f"👋 Welcome to Nexora VIP Gateway, {user}!\n\n"
        "Automate your VIP channel subscriptions seamlessly.\n"
        "Click below to get started or manage your channel."
    )
    
    keyboard = [
        [InlineKeyboardButton("💳 Subscribe to VIP Group", callback_data="sub")],
        [InlineKeyboardButton("⚙️ Setup Bot for My Channel", callback_data="setup")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

if __name__ == '__main__':
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable not set!")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()
