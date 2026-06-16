import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = os.environ.get("BOT_TOKEN")

WORKOUTS = {
    "A": [
        {"name": "חימום - הליכה מהירה / אליפטיקל", "sets": 1, "reps": "5-10 דקות", "video": "https://www.youtube.com/watch?v=__mMcqnGlGc"},
        {"name": "לחיצת רגליים - Leg Press", "sets": 3, "reps": "10-12", "video": "https://www.youtube.com/watch?v=IZxyjW7MPJQ"},
        {"name": "משיכת פולי עליון - Lat Pulldown", "sets": 3, "reps": "10-12", "video": "https://www.youtube.com/watch?v=CAwf7n6Luuc"},
        {"name": "לחיצת חזה - Dumbbell Press", "sets": 3, "reps": "10-12", "video": "https://www.youtube.com/watch?v=VmB1G1K7v94"},
        {"name": "הרמת זרועות לצדדים - Lateral Raises", "sets": 3, "reps": "12-15", "video": "https://www.youtube.com/watch?v=3VcKaXpzqRo"},
        {"name": "כפיפת רגליים - Leg Curl", "sets": 2, "reps": "12-15", "video": "https://www.youtube.com/watch?v=1Tq3QdYUuHs"},
        {"name": "כפיפת ברכיים - Bicep Curls", "sets": 2, "reps": "12-15", "video": "https://www.youtube.com/watch?v=ykJmrZ5v0Oo"},
        {"name": "פשיטת מרפקים - Triceps Pushdown", "sets": 2, "reps": "12-15", "video": "https://www.youtube.com/watch?v=2-LAMcpzODU"},
        {"name": "פלאנק", "sets": 3, "reps": "30-60 שניות", "video": "https://www.youtube.com/watch?v=ASdvN_XEl_c"},
    ]
}

def init_db():
    conn = sqlite3.connect("/tmp/gym.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        workout_type TEXT,
        exercise TEXT,
        weight REAL,
        sets INTEGER,
        reps TEXT
    )''')
    conn.commit()
    conn.close()

def get_last_weight(exercise):
    conn = sqlite3.connect("/tmp/gym.db")
    c = conn.cursor()
    c.execute('''SELECT weight, date FROM workouts WHERE exercise = ? ORDER BY date DESC LIMIT 1''', (exercise,))
    result = c.fetchone()
    conn.close()
    return result

def save_exercise(date, workout_type, exercise, weight, sets, reps):
    conn = sqlite3.connect("/tmp/gym.db")
    c = conn.cursor()
    c.execute('''INSERT INTO workouts (date, workout_type, exercise, weight, sets, reps) VALUES (?, ?, ?, ?, ?, ?)''',
              (date, workout_type, exercise, weight, sets, reps))
    conn.commit()
    conn.close()

CHOOSE_WORKOUT, DO_EXERCISE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
keyboard = [[
    InlineKeyboardButton("💪 התחל אימון", callback_data="workout_A")
]]
    await update.message.reply_text(
        "שלום! 👋\nבחר איזה אימון אתה עושה היום:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_WORKOUT

async def choose_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    workout_type = query.data.split("_")[1]
    context.user_data["workout_type"] = workout_type
    context.user_data["exercise_index"] = 0
    context.user_data["exercises"] = WORKOUTS[workout_type]
    from datetime import datetime
    context.user_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    await query.edit_message_text(f"מעולה! מתחילים אימון {workout_type} 🔥")
    await show_exercise(update, context)
    return DO_EXERCISE

async def show_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = context.user_data["exercise_index"]
    exercises = context.user_data["exercises"]
    if idx >= len(exercises):
        await finish_workout(update, context)
        return
    ex = exercises[idx]
    last = get_last_weight(ex["name"])
    last_text = f"\n📊 *בפעם הקודמת:* {last[0]} ק\"ג ({last[1]})" if last else "\n📊 *בפעם הקודמת:* אין מידע עדיין"
    text = (
        f"*תרגיל {idx+1}/{len(exercises)}*\n"
        f"🏋️ *{ex['name']}*\n"
        f"📋 {ex['sets']} סטים × {ex['reps']} חזרות"
        f"{last_text}\n\n"
        f"[▶️ צפה בסרטון]({ex['video']})\n\n"
        f"כמה ק\"ג עשית? (הכנס מספר)"
    )
    keyboard = [[InlineKeyboardButton("⏭️ דלג על תרגיל", callback_data="skip")]]
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def enter_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("בבקשה הכנס מספר בלבד (למשל: 50 או 22.5)")
        return DO_EXERCISE
    idx = context.user_data["exercise_index"]
    ex = context.user_data["exercises"][idx]
    save_exercise(context.user_data["date"], context.user_data["workout_type"], ex["name"], weight, ex["sets"], ex["reps"])
    await update.message.reply_text(f"✅ נשמר! {ex['name']}: {weight} ק\"ג")
    context.user_data["exercise_index"] += 1
    await show_exercise(update, context)
    return DO_EXERCISE

async def skip_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["exercise_index"] += 1
    await show_exercise(update, context)
    return DO_EXERCISE

async def finish_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎉 *כל הכבוד! סיימת את האימון!*\n\nלאימון הבא שלח /start"
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(text, parse_mode="Markdown")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_WORKOUT: [CallbackQueryHandler(choose_workout, pattern="^workout_")],
            DO_EXERCISE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_weight),
                CallbackQueryHandler(skip_exercise, pattern="^skip$"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv_handler)
    print("הבוט רץ...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
