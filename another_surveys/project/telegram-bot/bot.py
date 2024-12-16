import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from kafka import KafkaProducer
from pymongo import MongoClient
from io import BytesIO
import json
import base64
from prometheus_client import start_http_server, Summary


# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=['broker-1:29091', 'broker-2:29092', 'broker-3:29093'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Подключение к MongoDB
client = MongoClient('mongodb://mongodb:27017/')
db = client['telegram_bot']
users_collection = db['users']

# Определение этапов
NAME, AGE, PHOTO = range(3)

def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Привет! Как тебя зовут?')
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    user_data = {"user_id": update.message.from_user.id, "name": update.message.text}
    update.message.reply_text(f'Приятно познакомиться, {update.message.text}! Сколько тебе лет?')
    context.user_data['user_data'] = user_data
    return AGE

def get_age(update: Update, context: CallbackContext) -> int:
    context.user_data['user_data']['age'] = update.message.text
    update.message.reply_text('Теперь пришли мне свое фото.')
    return PHOTO

def get_photo(update: Update, context: CallbackContext) -> int:
    photo_file = update.message.photo[-1].get_file()
    photo_data = photo_file.download_as_bytearray()

    # Преобразуем photo_data в base64 строку
    context.user_data['user_data']['photo'] = base64.b64encode(photo_data).decode('utf-8')

    # Отправка данных в Kafka
    producer.send('user_profiles', context.user_data['user_data'])
    producer.flush()
    logger.info("Данные пользователя отправлены в Kafka: %s", context.user_data['user_data'])

    update.message.reply_text('Спасибо! Твоя анкета сохранена.')
    return ConversationHandler.END

def get_profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})

    if user_data:
        name = user_data.get('name')
        age = user_data.get('age')
        update.message.reply_text(f"Имя: {name}\nВозраст: {age}")

        if 'photo' in user_data:
            photo_bytes = BytesIO(base64.b64decode(user_data['photo']))
            update.message.reply_photo(photo=photo_bytes)
    else:
        update.message.reply_text("Анкета не найдена. Пожалуйста, заполните её.")

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Операция отменена.')
    return ConversationHandler.END

def error(update: Update, context: CallbackContext) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main() -> None:
    updater = Updater("7579659104:AAEl5gaUR_ths-ACG9necIl200WIbA7wSN4", use_context=True)  # Не забудьте заменить на токен вашего бота

    dp = updater.dispatcher

    # Настройка ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, get_name)],
            AGE: [MessageHandler(Filters.text & ~Filters.command, get_age)],
            PHOTO: [MessageHandler(Filters.photo, get_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler("get_profile", get_profile))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()

# Создайте метрики
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')

# Запустите HTTP сервер для метрик
start_http_server(8000)  # Порт, на котором будут доступны метрики


if __name__ == '__main__':
    main()

