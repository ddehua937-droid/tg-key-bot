import os
import csv
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CallbackQueryHandler,
    CommandHandler, filters, ContextTypes, ConversationHandler
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID  = os.getenv("SHEET_ID")
PORT      = int(os.getenv("PORT", 8080))

SHEETS = {
    "收银台查询": "0",
    "9494查询": "103160501",
    "数字人民币查询": "133972497",
    "强盛查询": "690514313",
}

WAITING_KEY = 1

class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass

def run_http():
    HTTPServer(("0.0.0.0", PORT), KeepAlive).serve_forever()

def fetch_sheet_by_gid(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return list(csv.reader(r.read().decode("utf-8").splitlines()))

def lookup_key(key: str, gid: str):
    rows = fetch_sheet_by_gid(gid)
    if not rows:
        return None
    headers = rows[0]
    for row in rows[1:]:
        if row and row[0].strip() == key.strip():
            return headers, row
    return None

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=f"sheet_{gid}")] for name, gid in SHEETS.items()]
    markup = InlineKeyboardMarkup(keyboard)
    text = "👋 欢迎使用工资查询系统！\n\n请选择您要查询的工资表："
    if update.message:
        await update.message.reply_text(text, reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_menu(update, context)
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("sheet_"):
        gid = query.data.replace("sheet_", "")
        name = next((n for n, g in SHEETS.items() if g == gid), gid)
        context.user_data["gid"] = gid
        context.user_data["sheet_name"] = name
        await query.edit_message_text(f"{name}\n\n请输入您的查询密钥：")
        return WAITING_KEY
    elif query.data == "back":
        await show_menu(update, context)
        return ConversationHandler.END

async def handle_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip()
    gid = context.user_data.get("gid")
    sheet_name = context.user_data.get("sheet_name", "")
    keyboard = [[InlineKeyboardButton("🔄 重新选择工资表", callback_data="back")]]
    markup = InlineKeyboardMarkup(keyboard)
    if not gid:
        await update.message.reply_text("⚠️ 请先选择工资表。", reply_markup=markup)
        return ConversationHandler.END
    try:
        result = lookup_key(key, gid)
    except Exception as e:
        print(f"查询出错: {e}")
        await update.message.reply_text("⚠️ 查询出错，请稍后重试。", reply_markup=markup)
        return ConversationHandler.END
    if result is None:
        await update.message.reply_text("❌ 密钥无效，请检查后重试。", reply_markup=markup)
    else:
        headers, row = result
        lines = []
        for i, header in enumerate(headers):
            value = row[i] if i < len(row) else ""
            if value.strip() not in ("", "0"):
                lines.append(f"{header}: {value}")
        await update.message.reply_text(
            f"✅ {sheet_name} 查询成功：\n\n" + "\n".join(lines),
            reply_markup=markup
        )
    return ConversationHandler.END

def main():
    threading.Thread(target=run_http, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_handler)
        ],
        states={
            WAITING_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_key),
                CallbackQueryHandler(button_handler)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    print("✅ Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
