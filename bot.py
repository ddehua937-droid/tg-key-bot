import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ── 环境变量 ──────────────────────────────────────
BOT_TOKEN       = os.getenv("BOT_TOKEN")
SHEET_ID        = os.getenv("SHEET_ID")          # Google Sheet 的ID（URL中间那串）
GOOGLE_CREDS    = os.getenv("GOOGLE_CREDS")       # service account JSON 内容（整个字符串）
PORT            = int(os.getenv("PORT", 8080))

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

# ── Google Sheet 连接 ─────────────────────────────
def get_sheet():
    import json
    creds_dict = json.loads(GOOGLE_CREDS)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

# ── 查密钥 ────────────────────────────────────────
def lookup_key(key: str):
    """
    返回 (headers, row_values) 或 None（未找到）
    headers: 第一行标题列表
    row_values: 密钥对应行的数据列表
    """
    sheet = get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
        return None

    headers = all_rows[0]       # 第一行：标题
    for row in all_rows[1:]:    # 从第二行开始找
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

    # 拼接：字段名: 值
    lines = []
    for i, header in enumerate(headers):
        value = row[i] if i < len(row) else ""
        lines.append(f"{header}: {value}")

    reply = "\n".join(lines)
    await update.message.reply_text(reply)

# ── 启动 ──────────────────────────────────────────
def main():
    # 先启动保活服务
    threading.Thread(target=run_http, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot 启动成功")
    app.run_polling()

if __name__ == "__main__":
    main()
