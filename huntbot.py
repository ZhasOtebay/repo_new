import json
import os
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
from dotenv import load_dotenv
import pandas as pd
from io import BytesIO

# Загружаем переменные окружения
load_dotenv()

# Загружаем шаблон вопросов
with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

# Конфигурация для бота и админского чата
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы состояний
SECTION1, SECTION2 = range(2)

# Начало опроса
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Давайте начнем опрос по охоте.")
    context.user_data['responses'] = []
    await update.message.reply_text(questions['section1_questions'][0])  # Первый вопрос
    return SECTION1

# Обработка ответов на вопросы
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_response = update.message.text
    context.user_data['responses'].append(user_response)
    
    current_question_index = len(context.user_data['responses'])
    if current_question_index < len(questions['section1_questions']):
        await update.message.reply_text(questions['section1_questions'][current_question_index])
        return SECTION1
    else:
        # После завершения всех вопросов сразу переходим к формированию Excel
        await send_excel_to_admin(update, context)
        return SECTION2

# Генерация вертикальной таблицы Excel и отправка с использованием номера лицензии в имени файла
async def send_excel_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем все ответы пользователя
    responses = context.user_data['responses']
    questions_list = questions['section1_questions']  # Список вопросов

    # Извлекаем номер лицензии для использования в имени файла
    license_number = responses[2]  # Вопрос 3 - номер лицензии
    
    # Преобразуем ответы в вертикальный формат
    data = {'Вопрос': questions_list, 'Ответ': responses}

    # Создаем DataFrame
    df = pd.DataFrame(data)
    
    # Сохраняем в буфер
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    
    # Имя файла с номером лицензии
    filename = f"survey_results_{license_number}.xlsx"
    
    # Отправляем Excel файл администратору
    await context.bot.send_document(ADMIN_CHAT_ID, buffer, filename=filename)
    
    # Подтверждаем завершение опроса пользователю
    await update.message.reply_text("Спасибо за участие в опросе! Ваши данные были успешно отправлены.")
    return ConversationHandler.END

# Завершение опроса
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Опрос был отменен.")
    return ConversationHandler.END

# Главная настройка бота
if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Конфигурируем обработчик для опроса
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SECTION1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response)],
            SECTION2: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_excel_to_admin)],  # Только отправка Excel
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

