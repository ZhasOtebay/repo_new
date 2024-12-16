from kafka import KafkaConsumer
from pymongo import MongoClient
import json
import logging
from prometheus_client import start_http_server, Summary

# Создайте метрики
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')

# Запустите HTTP сервер для метрик
start_http_server(8001)  # Порт, на котором будут доступны метрики

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Подключение к MongoDB
client = MongoClient('mongodb://mongodb:27017/')
db = client['telegram_bot']
collection = db['users']

# Kafka Consumer
consumer = KafkaConsumer(
    'user_profiles',
    bootstrap_servers=['broker-1:29091', 'broker-2:29092', 'broker-3:29093'],
    value_deserializer=lambda x: json.loads(x.decode('utf-8')),
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='user_profile_group'
)

# Обработка сообщений
try:
    for message in consumer:
        user_profile = message.value
        # Сохранение профиля пользователя в MongoDB
        collection.insert_one(user_profile)
        logger.info(f"Сохранен профиль пользователя: {user_profile}")

except Exception as e:
    logger.error(f"Произошла ошибка: {e}")

finally:
    consumer.close()
    client.close()

