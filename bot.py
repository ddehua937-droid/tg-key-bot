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

# ── 获取所有工作表的 gid ──────────────────────────
def get_sheet_gids():
    """从 Sheet 的 HTML 页面抓取所有 tab 的 gid"""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response:
        html = response.read().decode("utf-8")
    
    import re
    gids = re.findall(r'"gid=(\d+)"', html)
    # 去重并保持顺序
    seen = set()
    result = []
    for g in gids:
        if g not in seen:
            seen.add(g)
            result.append(g)
    return result if result else ["0"]

# ── 读取某个工作表（CSV方式）────────────────────────
def fetch_sheet_by_gid(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    with urllib.request.urlopen(url) as response:
        content = response.read().decode("utf-8")
    reader = csv.reader(content.splitlines())
    return list(reader)

# ── 查密钥（遍历所有工作表）──────────────────────────
def lookup_key(key: str):
    try:
        gids = get_sheet_gids()
    except:
        gids = ["0"]  # 抓取失败就只查第一个表

    for gid in gids:
        try:
            rows = fetch_sheet_by_gid(gid)
            if not rows:
                continue
            headers = rows[0]
            for row in rows[1:]:
                if row and row[0].strip() == key.strip():
                    return headers, row
        except:
            continue
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
