import os
import logging
import sqlite3
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Database setup
conn = sqlite3.connect("trading.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS portfolio (
                user_id INTEGER,
                coin TEXT,
                amount REAL,
                buy_price REAL
            )""")
conn.commit()

STARTING_BALANCE = 10000

# Helper functions
def get_price(coin="bitcoin", vs="usd"):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies={vs}&include_24hr_change=true"
    r = requests.get(url).json()
    return r.get(coin, {}).get(vs, None)

def get_balance(user_id):
    c.execute("SELECT SUM(amount*buy_price) FROM portfolio WHERE user_id=?", (user_id,))
    invested = c.fetchone()[0] or 0
    return STARTING_BALANCE - invested

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["English", "العربية"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        "Welcome to DRTrading Bot! Please choose a language.\n"
        "أهلاً بك في بوت DRTrading! الرجاء اختيار اللغة.",
        reply_markup=reply_markup
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /price bitcoin")
        return
    coin = context.args[0].lower()
    p = get_price(coin)
    if p:
        await update.message.reply_text(f"{coin.upper()} price: ${p}")
    else:
        await update.message.reply_text("Coin not found.")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /buy coin amount")
        return
    coin = context.args[0].lower()
    amount = float(context.args[1])
    price = get_price(coin)
    if not price:
        await update.message.reply_text("Coin not found.")
        return
    user_id = update.effective_user.id
    balance = get_balance(user_id)
    cost = price * amount
    if cost > balance:
        await update.message.reply_text("Not enough balance.")
        return
    c.execute("INSERT INTO portfolio (user_id, coin, amount, buy_price) VALUES (?, ?, ?, ?)",
              (user_id, coin, amount, price))
    conn.commit()
    await update.message.reply_text(f"Bought {amount} {coin.upper()} at ${price} each.")

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /sell coin amount")
        return
    coin = context.args[0].lower()
    amount = float(context.args[1])
    user_id = update.effective_user.id
    c.execute("SELECT amount, buy_price FROM portfolio WHERE user_id=? AND coin=?", (user_id, coin))
    row = c.fetchone()
    if not row or row[0] < amount:
        await update.message.reply_text("You don't own enough of this coin.")
        return
    price = get_price(coin)
    if not price:
        await update.message.reply_text("Coin not found.")
        return
    # Update portfolio
    new_amount = row[0] - amount
    if new_amount == 0:
        c.execute("DELETE FROM portfolio WHERE user_id=? AND coin=?", (user_id, coin))
    else:
        c.execute("UPDATE portfolio SET amount=? WHERE user_id=? AND coin=?", (new_amount, user_id, coin))
    conn.commit()
    revenue = amount * price
    await update.message.reply_text(f"Sold {amount} {coin.upper()} at ${price} each. Revenue: ${revenue}")

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT coin, amount, buy_price FROM portfolio WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("Your portfolio is empty.")
        return
    msg = "Your Portfolio:\n"
    for coin, amount, buy_price in rows:
        current_price = get_price(coin)
        current_value = current_price * amount
        invested = buy_price * amount
        profit_loss = current_value - invested
        msg += f"{coin.upper()}: {amount} | Current: ${current_value:.2f} | P/L: ${profit_loss:.2f}\n"
    await update.message.reply_text(msg)

# Main
def main():
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("portfolio", portfolio))

    app.run_polling()

if __name__ == "__main__":
    main()
