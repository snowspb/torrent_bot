import os
import requests
import logging
from bs4 import BeautifulSoup
from cachetools import cached, TTLCache
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Данные для авторизации на rutracker.org (лучше использовать переменные окружения)
RUTRACKER_LOGIN = os.getenv("RUTRACKER_LOGIN", "snowspb")  # Замените на ваш логин
RUTRACKER_PASSWORD = os.getenv("RUTRACKER_PASSWORD", "1TV3o")  # Замените на ваш пароль

# Сессия для сохранения cookies
session = requests.Session()

# Кэширование результатов поиска на 5 минут (300 секунд)
cache = TTLCache(maxsize=100, ttl=300)

@cached(cache)
def search_rutracker(query):
    try:
        url = "https://rutracker.org/forum/tracker.php"
        params = {"nm": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        logger.info(f"Выполняется поиск по запросу: {query}")
        response = session.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()  # Проверка на ошибки HTTP
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for row in soup.select('tr.tCenter.hl-tr'):
            title = row.select_one('td.t-title-col > div > a.tLink')
            if title:
                title_text = title.text.strip()
                link = "https://rutracker.org/forum/" + title['href']
                magnet_link = row.select_one('a.magnet-link')
                if magnet_link:
                    magnet_url = magnet_link['href']
                else:
                    magnet_url = None

                # Добавляем результат без категории
                results.append({"title": title_text, "link": link, "magnet": magnet_url})

        logger.info(f"Найдено результатов: {len(results)}")
        return results
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при поиске на rutracker.org: {e}")
        return []

# Функция для авторизации на rutracker.org
def login_to_rutracker():
    try:
        login_url = "https://rutracker.org/forum/login.php"
        payload = {
            "login_username": RUTRACKER_LOGIN,
            "login_password": RUTRACKER_PASSWORD,
            "login": "Вход"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = session.post(login_url, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info("Авторизация на rutracker.org прошла успешно!")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка авторизации на rutracker.org: {e}")
        return False

# Функция для получения подробной информации о торренте
def get_torrent_details(link):
    try:
        logger.info(f"Загружаем подробную информацию по ссылке: {link}")
        response = session.get(link, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Пример извлечения подробной информации (зависит от структуры страницы)
        details = soup.select_one('div.post_body')  # Основной блок с описанием
        if details:
            return details.text.strip()
        return "Подробная информация не найдена."
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при загрузке страницы торрента: {e}")
        return "Не удалось загрузить подробную информацию."

# Функция для поиска magnet-ссылки на странице торрента
def find_magnet_link(link):
    try:
        logger.info(f"Ищем magnet-ссылку на странице: {link}")
        response = session.get(link, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Ищем magnet-ссылку в различных местах
        magnet_link = soup.select_one('a.magnet-link')
        if not magnet_link:
            # Если ссылка не найдена через класс, ищем по тексту или атрибуту href
            magnet_link = soup.find('a', href=lambda x: x and x.startswith('magnet:'))

        if magnet_link:
            return magnet_link['href']
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при поиске magnet-ссылки: {e}")
        return None

# Функция для ограничения длины текста
def truncate_text(text, max_length=500):
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Пользователь {update.message.from_user.username} запустил бота.")
    # Создаем меню с кнопками
    keyboard = [
        ["🔍 Поиск торрентов"],
        ["ℹ️ Помощь", "📚 О боте"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=reply_markup)

# Функция для создания клавиатуры с пагинацией и номерами страниц
def create_pagination_keyboard(results, page=0, per_page=5):
    keyboard = []
    start = page * per_page
    end = start + per_page
    for result in results[start:end]:
        keyboard.append([InlineKeyboardButton(result["title"], callback_data=f"torrent_{results.index(result)}")])

    # Кнопки пагинации
    total_pages = (len(results) + per_page - 1) // per_page
    pagination_buttons = []

    if page > 0:
        pagination_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page - 1}"))

    # Кнопки с номерами страниц
    for i in range(max(0, page - 2), min(total_pages, page + 3)):
        if i == page:
            pagination_buttons.append(InlineKeyboardButton(f"• {i + 1} •", callback_data=f"page_{i}"))
        else:
            pagination_buttons.append(InlineKeyboardButton(str(i + 1), callback_data=f"page_{i}"))

    if page < total_pages - 1:
        pagination_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page + 1}"))

    if pagination_buttons:
        keyboard.append(pagination_buttons)

    return InlineKeyboardMarkup(keyboard)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"Пользователь {update.message.from_user.username} отправил сообщение: {text}")

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
            context.user_data["page"] = 0  # Начинаем с первой страницы

            # Создаем клавиатуру с пагинацией
            reply_markup = create_pagination_keyboard(results)

            await update.message.reply_text("Результаты поиска:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Ничего не найдено.")

# Обработчик callback-кнопок
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.info(f"Пользователь {query.from_user.username} выбрал: {data}")

    if data.startswith("page_"):
        # Обработка пагинации
        page = int(data.split("_")[1])
        context.user_data["page"] = page

        # Обновляем клавиатуру с новой страницей
        results = context.user_data["results"]
        reply_markup = create_pagination_keyboard(results, page=page)

        await query.edit_message_text("Результаты поиска:", reply_markup=reply_markup)
    elif data.startswith("torrent_"):
        # Обработка выбора торрента
        index = int(data.split("_")[1])
        results = context.user_data["results"]
        selected_torrent = results[index]

        # Получаем подробную информацию о торренте
        details = get_torrent_details(selected_torrent["link"])

        # Если magnet-ссылка не была найдена при поиске, ищем её на странице торрента
        if not selected_torrent["magnet"]:
            selected_torrent["magnet"] = find_magnet_link(selected_torrent["link"])

        # Ограничиваем длину описания
        truncated_details = truncate_text(details)

        # Формируем сообщение с подробной информацией
        message = (
            f"Название: {selected_torrent['title']}\n"
            f"Magnet-ссылка для копирования:\n"
            f"<code>{selected_torrent['magnet']}</code>\n"
            f"Описание:\n{truncated_details}"
        )

        # Добавляем кнопку "Назад"
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{context.user_data['page']}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем новое сообщение с подробной информацией
        await query.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup)

# Основная функция
def main():
    # Ваш токен бота
    token = "7008517922:AAFTf1fAAjekuCLfjFwYZQl5sbtze-F1ew0"

    # Авторизация на rutracker.org
    if not login_to_rutracker():
        logger.error("Не удалось авторизоваться на rutracker.org. Проверьте логин и пароль.")
        return

    # Создаем приложение
    application = ApplicationBuilder().token(token).build()

    # Регистрируем обработчики команд и сообщений
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запускаем бота
    logger.info("Бот запущен.")
    application.run_polling()

if __name__ == "__main__":
    main()
