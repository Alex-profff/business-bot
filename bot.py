import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Состояния
CHOOSING_SERVICE, CHOOSING_DATE, CHOOSING_TIME, ENTERING_NAME, ENTERING_PHONE, CONFIRMING = range(6)

# Услуги
SERVICES = {
    "haircut": "✂️ Стрижка — 1500₽ (60 мин)",
    "manicure": "💅 Маникюр — 2000₽ (90 мин)",
    "massage": "💆 Массаж — 3000₽ (60 мин)",
    "facial": "🧖 Уход за лицом — 2500₽ (75 мин)",
}

TIME_SLOTS = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]

bookings = {}


def main_keyboard():
    return ReplyKeyboardMarkup(
        [["📅 Записаться", "📋 Мои записи"],
         ["❌ Отменить запись", "ℹ️ О нас"]],
        resize_keyboard=True
    )


def services_keyboard():
    buttons = [[InlineKeyboardButton(name, callback_data=f"srv_{key}")]
               for key, name in SERVICES.items()]
    return InlineKeyboardMarkup(buttons)


def dates_keyboard():
    buttons = []
    today = datetime.now()
    row = []
    for i in range(1, 8):
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        day_name = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date.weekday()]
        row.append(InlineKeyboardButton(f"{day_name} {date_str}", callback_data=f"dt_{date_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_srv")])
    return InlineKeyboardMarkup(buttons)


def times_keyboard(date):
    booked = [b["time"] for b in bookings.values() if b["date"] == date]
    buttons = []
    row = []
    for time in TIME_SLOTS:
        if time in booked:
            row.append(InlineKeyboardButton(f"❌ {time}", callback_data="busy"))
        else:
            row.append(InlineKeyboardButton(f"✅ {time}", callback_data=f"tm_{time}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_dt")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Добро пожаловать в наш салон!\n\n"
        "Я помогу вам записаться на услугу.\n"
        "Выберите действие:",
        reply_markup=main_keyboard()
    )


async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💼 Выберите услугу:",
        reply_markup=services_keyboard()
    )
    return CHOOSING_SERVICE


async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("srv_", "")
    context.user_data["service"] = SERVICES[key]
    await query.edit_message_text(
        f"✅ Услуга: {SERVICES[key]}\n\n📅 Выберите дату:",
        reply_markup=dates_keyboard()
    )
    return CHOOSING_DATE


async def back_to_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💼 Выберите услугу:", reply_markup=services_keyboard())
    return CHOOSING_SERVICE


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date = query.data.replace("dt_", "")
    context.user_data["date"] = date
    await query.edit_message_text(
        f"📅 Дата: {date}\n\n⏰ Выберите время:",
        reply_markup=times_keyboard(date)
    )
    return CHOOSING_TIME


async def back_to_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📅 Выберите дату:", reply_markup=dates_keyboard())
    return CHOOSING_DATE


async def busy_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("❌ Это время занято!", show_alert=True)
    return CHOOSING_TIME


async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time = query.data.replace("tm_", "")
    context.user_data["time"] = time
    await query.edit_message_text(f"⏰ Время: {time}\n\n👤 Введите ваше имя:")
    return ENTERING_NAME


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("📱 Введите номер телефона:")
    return ENTERING_PHONE


async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    d = context.user_data
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
         InlineKeyboardButton("❌ Отменить", callback_data="decline")]
    ])
    await update.message.reply_text(
        f"📋 Проверьте данные:\n\n"
        f"💼 {d['service']}\n"
        f"📅 {d['date']} в {d['time']}\n"
        f"👤 {d['name']}\n"
        f"📱 {d['phone']}",
        reply_markup=keyboard
    )
    return CONFIRMING


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data
    user_id = query.from_user.id
    booking_id = f"{user_id}_{datetime.now().strftime('%H%M%S')}"
    bookings[booking_id] = {
        "user_id": user_id,
        "service": d["service"],
        "date": d["date"],
        "time": d["time"],
        "name": d["name"],
        "phone": d["phone"]
    }
    await query.edit_message_text(
        f"✅ Запись подтверждена!\n\n"
        f"💼 {d['service']}\n"
        f"📅 {d['date']} в {d['time']}\n\n"
        f"Ждём вас! 😊"
    )
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 Новая запись!\n\n"
        f"💼 {d['service']}\n"
        f"📅 {d['date']} в {d['time']}\n"
        f"👤 {d['name']}\n"
        f"📱 {d['phone']}"
    )
    return ConversationHandler.END


async def decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("❌ Запись отменена.")
    return ConversationHandler.END


async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_b = {k: v for k, v in bookings.items() if v["user_id"] == user_id}
    if not user_b:
        await update.message.reply_text("У вас нет активных записей.")
        return
    text = "📋 Ваши записи:\n\n"
    for b in user_b.values():
        text += f"🔹 {b['service']}\n📅 {b['date']} в {b['time']}\n\n"
    await update.message.reply_text(text)


async def cancel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_b = {k: v for k, v in bookings.items() if v["user_id"] == user_id}
    if not user_b:
        await update.message.reply_text("У вас нет активных записей.")
        return
    buttons = [[InlineKeyboardButton(
        f"{b['date']} {b['time']}",
        callback_data=f"del_{k}"
    )] for k, b in user_b.items()]
    await update.message.reply_text(
        "Выберите запись для отмены:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def delete_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    booking_id = query.data.replace("del_", "")
    if booking_id in bookings:
        del bookings[booking_id]
        await query.edit_message_text("✅ Запись отменена!")
    else:
        await query.edit_message_text("❌ Запись не найдена.")


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏢 Наш салон красоты\n\n"
        "📍 Адрес: ул. Примерная, д. 1\n"
        "📞 Телефон: +7 (999) 123-45-67\n"
        "🕐 Работаем: 10:00 — 20:00\n\n"
        "Рады вас видеть! 😊"
    )


async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Запись отменена. Возвращаемся в главное меню.",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📅 Записаться$"), book_start)],
        states={
            CHOOSING_SERVICE: [CallbackQueryHandler(choose_service, pattern="^srv_"),
                               CallbackQueryHandler(back_to_services, pattern="^back_srv$")],
            CHOOSING_DATE: [CallbackQueryHandler(choose_date, pattern="^dt_"),
                           CallbackQueryHandler(back_to_dates, pattern="^back_dt$")],
            CHOOSING_TIME: [CallbackQueryHandler(choose_time, pattern="^tm_"),
                           CallbackQueryHandler(busy_time, pattern="^busy$"),
                           CallbackQueryHandler(back_to_dates, pattern="^back_dt$")],
            ENTERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(📋 Мои записи|❌ Отменить запись|ℹ️ О нас|📅 Записаться)$"), enter_name),
                           MessageHandler(filters.Regex("^(📋 Мои записи|❌ Отменить запись|ℹ️ О нас|📅 Записаться)$"), cancel_conv)],
            ENTERING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(📋 Мои записи|❌ Отменить запись|ℹ️ О нас|📅 Записаться)$"), enter_phone),
                            MessageHandler(filters.Regex("^(📋 Мои записи|❌ Отменить запись|ℹ️ О нас|📅 Записаться)$"), cancel_conv)],
            CONFIRMING: [CallbackQueryHandler(confirm, pattern="^confirm$"),
                        CallbackQueryHandler(decline, pattern="^decline$")],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel_conv)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^📋 Мои записи$"), my_bookings))
    app.add_handler(MessageHandler(filters.Regex("^❌ Отменить запись$"), cancel_menu))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ О нас$"), about))
    app.add_handler(CallbackQueryHandler(delete_booking, pattern="^del_"))

    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
