import os
import pandas as pd
from pymongo import MongoClient
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Определяем состояния для опроса
SURVEY, ANSWER = range(2)

# Устанавливаем соединение с MongoDB
client = MongoClient('mongodb://mongodb:27017/')
db = client.survey_db
collection = db.responses

# Вопросы опросника для каждого языка
questions = {
    'kz': [
        "Қай табиғи паркке бардыңыз?",
        "Паркте қанша күн болдыңыз?",
        "Сіздің тобыңызда қанша адам болды?",
        "Сіз паркті аралау кезінде қай мезгілде болдыңыз?",
        "Сіз паркте қандай әрекетті таңдадыңыз?",
        "Паркта табиғаттың сақталу деңгейін қалай бағалайсыз?",
        "Парке қалай жеттіңіз?",
        "Сіздің сапарыңызда не ұнады?",
        "Бұл паркті басқа адамдарға ұсынар ма едіңіз?",
        "Паркті аралауды жақсартуға қандай ұсыныстарыңыз бар?",
    ],
    'ru': [
        "Какой природный парк вы посетили?",
        "Сколько дней вы провели в парке?",
        "Сколько человек было в вашей группе?",
        "Какое время года было во время вашего визита?",
        "Какой вид деятельности вы предпочли во время посещения парка?",
        "Как вы оцениваете уровень сохранности природы в парке?",
        "Какой транспорт вы использовали для добирания до парка?",
        "Что вам понравилось больше всего в вашем визите?",
        "Порекомендовали бы вы этот парк другим?",
        "Есть ли у вас какие-либо предложения для улучшения посещения парка?",
    ],
    'en': [
        "What nature park did you visit?",
        "How many days did you spend in the park?",
        "How many people were in your group?",
        "What season was it during your visit?",
        "What activity did you prefer during your visit to the park?",
        "How would you rate the level of nature preservation in the park?",
        "What transportation did you use to get to the park?",
        "What did you like the most about your visit?",
        "Would you recommend this park to others?",
        "Do you have any suggestions for improving park visits?",
    ],
}

# Сообщения для каждого языка
responses = {
    'start': {
        'kz': "Қош келдіңіз! /survey деп жазу арқылы сауалнаманы бастаңыз.",
        'ru': "Добро пожаловать! Напишите /survey, чтобы начать опрос.",
        'en': "Welcome! Type /survey to start the survey.",
    },
    'language_prompt': {
        'kz': "Тілді таңдаңыз: 1. Қазақша 2. Русский 3. English",
        'ru': "Выберите язык: 1. Казахский 2. Русский 3. Английский",
        'en': "Choose a language: 1. Kazakh 2. Russian 3. English",
    },
    'empty_answer': {
        'kz': "Жауап бос бола алмайды. Жауап енгізіңіз.",
        'ru': "Ответ не может быть пустым. Пожалуйста, введите ответ.",
        'en': "Answer cannot be empty. Please provide an answer.",
    },
    'thank_you': {
        'kz': "Рахмет! Сіздің кодыңыз: {code}",
        'ru': "Спасибо! Ваш код: {code}",
        'en': "Thank you! Your code: {code}",
    },
    'survey_cancelled': {
        'kz': "Сауалнама тоқтатылды.",
        'ru': "Опрос отменен.",
        'en': "Survey canceled.",
    },
}

# Функция стартового сообщения
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get('language', 'ru')  # По умолчанию русский
    await update.message.reply_text(responses['start'][language])

# Функция для начала опроса
async def survey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get('language', 'ru')  # По умолчанию русский
    await update.message.reply_text(responses['language_prompt'][language])
    return SURVEY

# Функция для обработки выбора языка
async def language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language_choice = update.message.text
    if language_choice == '1':
        context.user_data['language'] = 'kz'
    elif language_choice == '2':
        context.user_data['language'] = 'ru'
    elif language_choice == '3':
        context.user_data['language'] = 'en'
    else:
        await update.message.reply_text("Неправильный выбор. Пожалуйста, выберите 1, 2 или 3.")
        return SURVEY

    # Генерация кода анкеты
    context.user_data['code'] = f"CODE-{update.effective_user.id}"
    context.user_data['current_question'] = 0

    await update.message.reply_text(questions[context.user_data['language']][context.user_data['current_question']])
    return ANSWER

# Функция для обработки ответов
async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data['language']
    current_question_index = context.user_data['current_question']

    # Проверка на пустой ответ
    if not update.message.text:
        await update.message.reply_text(responses['empty_answer'][language])
        return ANSWER

    # Сохраняем ответ в базу данных
    response = {
        'user_id': update.effective_user.id,
        'language': language,
        'code': context.user_data['code'],  # Сохраняем код анкеты
        'responses': [{
            'question': questions[language][current_question_index],
            'answer': update.message.text
        }]
    }
    collection.insert_one(response)

    # Переход к следующему вопросу
    context.user_data['current_question'] += 1
    if context.user_data['current_question'] < len(questions[language]):
        await update.message.reply_text(questions[language][context.user_data['current_question']])
        return ANSWER
    else:
        # Завершение опроса
        code = context.user_data['code']
        user_name = update.effective_user.first_name  # Используем имя пользователя как имя опрошенного

        # Отправка кода и имени в группу
        admin_chat_id = -1002481061085  # Замените на ID вашей группы
        await context.bot.send_message(chat_id=admin_chat_id, text=f"Пользователь: {user_name}, Код: {code}")

        await update.message.reply_text(responses['thank_you'][language].format(code=code))
        return ConversationHandler.END

# Функция для выгрузки данных в CSV
async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = list(collection.find({}, {"_id": 0, "responses": 1}))  # Извлечение только нужных полей
    df = pd.DataFrame(data)
    csv_file = '/tmp/responses.csv'
    df.to_csv(csv_file, index=False)
    await update.message.reply_document(document=open(csv_file, 'rb'))

# Функция для отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get('language', 'ru')  # По умолчанию русский
    await update.message.reply_text(responses['survey_cancelled'][language])
    return ConversationHandler.END

# Функция для запроса анкеты по коду
async def request_survey_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите код анкеты. Пример: /get_survey CODE-123")
        return

    code = context.args[0]
    survey_data = collection.find_one({"code": code})

    if survey_data:
        # Формируем ответ с данными анкеты
        response_message = f"Анкета по коду {code}:\n"
        response_message += f"Язык: {survey_data['language']}\n"
        response_message += f"Вопросы и ответы:\n"
        for item in survey_data['responses']:
            response_message += f"{item['question']}: {item['answer']}\n"
        await update.message.reply_text(response_message)
    else:
        await update.message.reply_text("Анкета с таким кодом не найдена.")

# Функция для экспорта всех анкет
async def export_all_surveys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Извлечение всех анкет из базы данных
    surveys = list(collection.find({}, {"_id": 0, "code": 1, "language": 1, "responses": 1}))

    if surveys:
        # Формирование списка всех анкет и их ответов для CSV
        all_data = []
        for survey in surveys:
            for response in survey['responses']:
                all_data.append({
                    'code': survey['code'],
                    'language': survey['language'],
                    'question': response['question'],
                    'answer': response['answer']
                })

        # Формирование CSV-файла для всех анкет
        csv_file = '/tmp/all_surveys_export.csv'
        df = pd.DataFrame(all_data)

        df.to_csv(csv_file, index=False)

        # Отправка файла в чат
        await update.message.reply_document(document=open(csv_file, 'rb'))
    else:
        await update.message.reply_text("Анкет в базе данных не найдено.")


# Функция для экспорта данных по коду анкеты
async def export_survey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите код анкеты. Пример: /export CODE-123")
        return

    code = context.args[0]
    survey_data = collection.find_one({"code": code})

    if survey_data:
        # Формирование CSV-файла
        csv_file = '/tmp/survey_export.csv'
        responses = survey_data['responses']
        df = pd.DataFrame(responses)

        df.to_csv(csv_file, index=False)

        # Отправка файла в чат
        await update.message.reply_document(document=open(csv_file, 'rb'))
    else:
        await update.message.reply_text(f"Анкета с кодом {code} не найдена.")




# Основная функция
def main():
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('survey', survey)],
        states={
            SURVEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_choice)],
            ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('export', export_csv))
    application.add_handler(CommandHandler('get_survey', request_survey_by_code))
    application.add_handler(CommandHandler("export", export_survey))
    application.add_handler(CommandHandler("export_all", export_all_surveys))
    application.add_handler(CommandHandler('start', survey))


    application.run_polling()

if __name__ == '__main__':
    main()


