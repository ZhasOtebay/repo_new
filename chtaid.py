import requests


TOKEN = '7972406602:AAF5CLu8uxNtSyoj6Us5lQe4qd3u17YUups'  # Замените на свой токен
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
response = requests.get(url)
updates = response.json()

# Выводим информацию о группах и чате
print(updates)
