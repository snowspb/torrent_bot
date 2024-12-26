import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Данные для авторизации на rutracker.org
RUTRACKER_LOGIN = "snowspb"  # Замените на ваш логин
RUTRACKER_PASSWORD = "1TV3o"  # Замените на ваш пароль

# Сессия для сохранения cookies
session = requests.Session()

# Функция для авторизации на rutracker.org
def login_to_rutracker():
    login_url = "https://rutracker.org/forum/login.php"
    payload = {
        "login_username": RUTRACKER_LOGIN,
        "login_password": RUTRACKER_PASSWORD,
        "login": "Вход"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = session.post(login_url, data=payload, headers=headers)
    if response.status_code == 200:
        print("Авторизация на rutracker.org прошла успешно!")
    else:
        print("Ошибка авторизации на rutracker.org.")

# Функция для поиска торрентов на rutracker.org
def search_rutracker(query):
    url = "https://rutracker.org/forum/tracker.php"
    params = {
        "nm": query  # Параметр поиска
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = session.get(url, params=params, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []
    for row in soup.select('tr.tCenter.hl-tr'):
        title = row.select_one('td.t-title-col > div > a.tLink')
        if title:
            title_text = title.text.strip()
            link = "https://rutracker.org/forum/" + title['href']
            # Ищем magnet-ссылку
            magnet_link = row.select_one('a.magnet-link')
            if magnet_link:
                magnet_url = magnet_link['href']
                results.append({"title": title_text, "link": link, "magnet": magnet_url})
            else:
                results.append({"title": title_text, "link": link, "magnet": None})

    return results

# Функция для получения подробной информации о торренте
def get_torrent_details(link):
    response = session.get(link)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Пример извлечения подробной информации (зависит от структуры страницы)
    details = soup.select_one('div.post_body')  # Основной блок с описанием
    if details:
        return details.text.strip()
    return "Подробная информация не найдена."

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаем меню с кнопками
    keyboard = [
        ["🔍 Поиск торрентов"],
        ["ℹ️ Помощь", "📚 О боте"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=reply_markup)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Поиск торрентов":
        await update.message.reply_text("Введите запрос для поиска торрентов на rutracker.org:")
    elif text == "ℹ️ Помощь":
        await update.message.reply_text("Этот бот позволяет искать торренты на rutracker.org. Просто введите запрос, и бот найдет подходящие результаты.")
    elif text == "📚 О боте":
        await update.message.reply_text("Этот бот создан для поиска торрентов на rutracker.org. Используйте кнопки для удобного взаимодействия.")
    else:
        # Поиск торрентов
        query = text
        results = search_rutracker(query)

        if results:
            # Сохраняем результаты в контексте
            context.user_data["results"] = results

            # Создаем клавиатуру с кнопками для выбора торрента
            keyboard = [
                [InlineKeyboardButton(result["title"], callback_data=str(index))]
                for index, result in enumerate(results[:5])  # Ограничиваем 5 результатами
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text("Выберите торрент:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Ничего не найдено.")

# Обработчик callback-кнопок
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Получаем выбранный торрент из сохраненных результатов
    index = int(query.data)
    results = context.user_data["results"]
    selected_torrent = results[index]

    # Получаем подробную информацию о торренте
    details = get_torrent_details(selected_torrent["link"])

    # Формируем сообщение с подробной информацией
    message = (
        f"Название: {selected_torrent['title']}\n"
        f"Ссылка: {selected_torrent['link']}\n"
        f"Magnet: {selected_torrent['magnet'] or 'Не найдена'}\n"
        f"Описание:\n{details}"
    )

    # Отправляем новое сообщение с подробной информацией
    await query.message.reply_text(message)

# Основная функция
def main():
    # Ваш токен бота
    token = "7008517922:AAFTf1fAAjekuCLfjFwYZQl5sbtze-F1ew0"

    # Авторизация на rutracker.org
    login_to_rutracker()

    # Создаем приложение
    application = ApplicationBuilder().token(token).build()

    # Регистрируем обработчики команд и сообщений
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()