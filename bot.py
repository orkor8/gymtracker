import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# --- הגדרות ---
import os
TOKEN = os.environ.get("BOT_TOKEN")

# --- תוכנית האימונים ---
WORKOUTS = {
    "A": [
        {"name": "לג פרס", "sets": 3, "reps": "12", "video": "https://www.youtube.com/watch?v=IZxyjW7MPJQ"},
        {"name": "בנץ' פרס דמבלס", "sets": 3, "reps": "10-12", "video": "https://www.youtube.com/watch?v=VmB1G1K7v94"},
        {"name": "כתפיים - Shoulder Press", "sets": 2, "reps": "12", "video": "https://www.youtube.com/watch?v=qEwKCR5JCog"},
        {"name": "פק דק / Cable Fly", "sets": 2, "reps": "12", "video": "https://www.youtube.com/watch?v=TAOfpADMBJo"},
        {"name": "פלאנק", "sets": 3, "reps": "30-40 שניות", "video": "https://www.youtube.com/watch?v=ASdvN_XEl_c"},
    ],
    "B": [
        {"name": "Leg Curl", "sets": 3, "reps": "12", "video": "https://www.youtube.com/watch?v=1Tq3QdYUuHs"},
        {"name": "Seated Row", "sets": 3, "reps": "10-12", "video": "https://www.youtube.com/watch?v=GZbfZ033f74"},
        {"name": "Lat Pulldown", "sets": 3, "reps": "12", "video": "https://www.youtube.com/watch?v=CAwf7n6Luuc"},
        {"name": "כפיפות מרפק - Bicep Curl", "sets": 2, "reps": "12", "video": "https://www.youtube.com/watch?v=ykJmrZ5v0Oo"},
        {"name": "Dead Bug", "sets": 3, "reps": "8 כל צד", "video": "https://www.youtube.com/watch?v=g_BYB0R-4Ws"},
    ]
}

# --- מסד נתונים ---
def init_db():
    conn = sqlite3.connect("gym.db")
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
    conn = sqlite3.connect("gym.db")
    c = conn.cursor()
    c.execute('''SELECT weight, date FROM workouts 
                 WHERE exercise = ? 
                 ORDER BY date DESC LIMIT 1''', (exercise,))
    result = c.fetchone()
    conn.close()
    return result

def save_exercise(date, workout_type, exercise, weight, sets, reps):
    conn = sqlite3.connect("gym.db")
    c = conn.cursor()
    c.execute('''INSERT INTO workouts (date, workout_type, exercise, weight, sets, reps)
                 VALUES (?, ?, ?, ?, ?, ?)''', (date, workout_type, exercise, weight, sets, reps))
    conn.commit()
    conn.close()

# --- States לשיחה ---
CHOOSE_WORKOUT, DO_EXERCISE, ENTER_WEIGHT = range(3)

# --- handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💪 אימון A", callback_data="workout_A"),
         InlineKeyboardButton("🏋️ אימון B", callback_data="workout_B")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "שלום! 👋\nבחר איזה אימון אתה עושה היום:",
        reply_markup=reply_markup
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
    
    last_text = ""
    if last:
        last_text = f"\n📊 *בפעם הקודמת:* {last[0]} ק\"ג ({last[1]})"
    else:
        last_text = "\n📊 *בפעם הקודמת:* אין מידע עדיין"
    
    text = (
        f"*תרגיל {idx+1}/{len(exercises)}*\n"
        f"🏋️ *{ex['name']}*\n"
        f"📋 {ex['sets']} סטים × {ex['reps']} חזרות"
        f"{last_text}\n\n"
        f"[▶️ צפה בסרטון]({ex['video']})\n\n"
        f"כמה ק\"ג עשית? (הכנס מספר)"
    )
    
    keyboard = [[InlineKeyboardButton("⏭️ דלג על תרגיל", callback_data="skip")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def enter_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("בבקשה הכנס מספר בלבד (למשל: 50 או 22.5)")
        return DO_EXERCISE
    
    idx = context.user_data["exercise_index"]
    exercises = context.user_data["exercises"]
    ex = exercises[idx]
    
    save_exercise(
        context.user_data["date"],
        context.user_data["workout_type"],
        ex["name"],
        weight,
        ex["sets"],
        ex["reps"]
    )
    
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
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

# --- הרצה ---
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
    app.run_polling()

if __name__ == "__main__":
    main()
