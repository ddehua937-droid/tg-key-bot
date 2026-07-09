import os
import csv
import re
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CallbackQueryHandler,
    CommandHandler, filters, ContextTypes, ConversationHandler
)

# ── 环境变量 ──────────────────────────────────────
BOT_TOKEN    = os.getenv("BOT_TOKEN")
SHEET_ID     = os.getenv("SHEET_ID")
SHEET_NAMES  = os.getenv("SHEET_NAMES", "Sheet1").split(",")
PORT         = int(os.getenv("PORT", 8080))

# ── 对话状态 ──────────────────────────────────────
WAITING_KEY = 1

# ── 保活 HTTP ─────────────────────────────────────
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, *args):
        pass

def run_http():
    HTTPServer(("0.0.0.0", PORT), KeepAlive).serve_forever()

# ── 读取工作表（按标签名）────────────────────────
def fetch_sheet_by_name(sheet_name):
    encoded_name = urllib.parse.quote(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response:
        content = response.read().decode("utf-8")
    return list(csv.reader(content.splitlines()))

# ── 查密钥（遍历所有标签名）──────────────────────
def lookup_key(key: str):
    for name in SHEET_NAMES:
        name = name.strip()
        try:
            rows = fetch_sheet_by_name(name)
            if not rows:
                continue
            headers = rows[0]
            for row in rows[1:]:
                if row and row[0].strip() == key.strip():
                    return headers, row
        except Exception as e:
            print(f"读取标签「{name}」失败: {e}")
            continue
    return None

# ── 主菜单 ────────────────────────────────────────
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 查询工资", callback_data="salary")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    text = "👋 欢迎使用！\n\n请选择您需要的服务："
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
    if query.data == "salary":
        await query.edit_message_text("💰 请输入您的工资查询密钥：")
        return WAITING_KEY
    elif query.data == "back":
        await show_menu(update, context)
        return ConversationHandler.END

async def handle_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip()
    result = lookup_key(key)
    keyboard = [[InlineKeyboardButton("🔙 返回主菜单", callback_data="back")]]
    markup = InlineKeyboardMarkup(keyboard)
    if result is None:
        await update.message.reply_text("❌ 密钥无效，请检查后重试。", reply_markup=markup)
    else:
        headers, row = result
        lines = []
        for i, header in enumerate(headers):
            value = row[i] if i < len(row) else ""
            lines.append(f"{header}: {value}")
        await update.message.reply_text("✅ 查询成功：\n\n" + "\n".join(lines), reply_markup=markup)
    return ConversationHandler.END

def main():
    threading.Thread(target=run_http, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
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
    app.add_handler(conv_handler)
    print("✅ Bot 启动成功")
    app.run_polling()

if __name__ == "__main__":
    main()
