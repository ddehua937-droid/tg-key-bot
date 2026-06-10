import os
import csv
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ── 环境变量 ──────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID  = os.getenv("SHEET_ID")
PORT      = int(os.getenv("PORT", 8080))

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

# ── 读取 Google Sheet（CSV方式）─────────────────────
def fetch_sheet():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
    with urllib.request.urlopen(url) as response:
        content = response.read().decode("utf-8")
    reader = csv.reader(content.splitlines())
    return list(reader)

# ── 查密钥 ────────────────────────────────────────
def lookup_key(key: str):
    rows = fetch_sheet()
    if not rows:
        return None
    headers = rows[0]
    for row in rows[1:]:
        if row and row[0].strip() == key.strip():
            return headers, row
    return None

# ── 消息处理 ──────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    result = lookup_key(user_input)

    if result is None:
        await update.message.reply_text("❌ 密钥无效，请检查后重试。")
        return

    headers, row = result
    lines = []
    for i, header in enumerate(headers):
        value = row[i] if i < len(row) else ""
        lines.append(f"{header}: {value}")

    await update.message.reply_text("\n".join(lines))

# ── 启动 ──────────────────────────────────────────
def main():
    threading.Thread(target=run_http, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot 启动成功")
    app.run_polling()

if __name__ == "__main__":
    main()
