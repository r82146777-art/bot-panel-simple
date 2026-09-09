from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "bot-panel-secret-key-change-in-production"

DB_NAME = "bots.db"
GENERATED_DIR = "generated"

os.makedirs(GENERATED_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            token TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            code TEXT NOT NULL,
            status TEXT DEFAULT 'stopped',
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    conn = get_db()
    bots = conn.execute("SELECT * FROM bots ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", bots=bots)

@app.route("/create/<platform>")
def create_form(platform):
    if platform not in ["telegram", "bale", "rubika"]:
        flash("پلتفرم نامعتبر است", "error")
        return redirect(url_for("index"))
    return render_template("form.html", platform=platform, bot=None)

@app.route("/edit/<int:bot_id>")
def edit_form(bot_id):
    conn = get_db()
    bot = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
    conn.close()
    if not bot:
        flash("ربات پیدا نشد", "error")
        return redirect(url_for("index"))
    return render_template("form.html", platform=bot["platform"], bot=bot)

@app.route("/save", methods=["POST"])
def save_bot():
    bot_id = request.form.get("bot_id")
    platform = request.form.get("platform")
    token = request.form.get("token", "").strip()
    owner_id = request.form.get("owner_id", "").strip()
    code = request.form.get("code", "").strip()

    if not token or not owner_id or not code:
        flash("همه فیلدها الزامی هستند", "error")
        return redirect(request.referrer or url_for("index"))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()

    if bot_id:  # ویرایش
        conn.execute(
            "UPDATE bots SET token=?, owner_id=?, code=?, status='stopped', updated_at=? WHERE id=?",
            (token, owner_id, code, now, bot_id)
        )
        flash("ربات با موفقیت ویرایش شد. دوباره استارت بزن.", "success")
        final_id = bot_id
    else:  # ایجاد جدید
        cursor = conn.execute(
            "INSERT INTO bots (platform, token, owner_id, code, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'stopped', ?, ?)",
            (platform, token, owner_id, code, now, now)
        )
        final_id = cursor.lastrowid
        flash("ربات با موفقیت ایجاد شد", "success")

    conn.commit()
    conn.close()

    # تولید فایل ربات
    generate_bot_file(final_id, platform, token, owner_id, code)

    return redirect(url_for("index"))

@app.route("/start/<int:bot_id>")
def start_bot(bot_id):
    conn = get_db()
    bot = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
    if bot:
        conn.execute("UPDATE bots SET status='running', updated_at=? WHERE id=?",
                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), bot_id))
        conn.commit()
        flash(f"ربات #{bot_id} استارت شد (وضعیت شبیه‌سازی شده)", "success")
    conn.close()
    return redirect(url_for("index"))

@app.route("/stop/<int:bot_id>")
def stop_bot(bot_id):
    conn = get_db()
    conn.execute("UPDATE bots SET status='stopped', updated_at=? WHERE id=?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), bot_id))
    conn.commit()
    conn.close()
    flash("ربات متوقف شد", "success")
    return redirect(url_for("index"))

@app.route("/delete/<int:bot_id>")
def delete_bot(bot_id):
    conn = get_db()
    conn.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()
    # حذف فایل تولیدشده
    file_path = os.path.join(GENERATED_DIR, f"bot_{bot_id}.py")
    if os.path.exists(file_path):
        os.remove(file_path)
    flash("ربات حذف شد", "success")
    return redirect(url_for("index"))

@app.route("/download/<int:bot_id>")
def download_bot(bot_id):
    filename = f"bot_{bot_id}.py"
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)

def generate_bot_file(bot_id, platform, token, owner_id, code):
    """تولید فایل پایتون آماده اجرا بر اساس پلتفرم"""
    if platform == "telegram":
        template = f'''# ربات تلگرام - تولید شده توسط پنل
# Bot ID: {bot_id}
# Owner ID: {owner_id}

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "{token}"
OWNER_ID = {owner_id}

# ==================== کد ربات شما ====================
{code}
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ربات روشن است!")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    # اگر در کد خودت هندلر تعریف کرده‌ای، اینجا اضافه کن
    print("ربات تلگرام در حال اجرا...")
    app.run_polling()

if __name__ == "__main__":
    main()
'''
    elif platform == "bale":
        template = f'''# ربات بله - تولید شده توسط پنل
# Bot ID: {bot_id}
# Owner ID: {owner_id}

# برای بله از کتابخانه python-bale-bot استفاده کنید:
# pip install python-bale-bot

from bale import Bot, Message

TOKEN = "{token}"
OWNER_ID = "{owner_id}"

bot = Bot(token=TOKEN)

# ==================== کد ربات شما ====================
{code}
# =====================================================

@bot.listen("message")
async def on_message(message: Message):
    if message.content == "/start":
        await message.reply("ربات بله روشن است!")

if __name__ == "__main__":
    print("ربات بله در حال اجرا...")
    bot.run()
'''
    else:  # rubika
        template = f'''# ربات روبیکا - تولید شده توسط پنل
# Bot ID: {bot_id}
# Owner ID: {owner_id}

# برای روبیکا از کتابخانه‌های موجود مثل rubka یا rubika-bot استفاده کنید
# pip install rubka

TOKEN = "{token}"
OWNER_ID = "{owner_id}"

# ==================== کد ربات شما ====================
{code}
# =====================================================

print("ربات روبیکا آماده است. کد خود را کامل کنید و اجرا کنید.")
print("توکن:", TOKEN)
print("Owner ID:", OWNER_ID)
'''

    file_path = os.path.join(GENERATED_DIR, f"bot_{bot_id}.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(template)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
