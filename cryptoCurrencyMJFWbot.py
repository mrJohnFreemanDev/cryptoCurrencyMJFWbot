import os
import re
import logging
import time
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv
import traceback
import asyncio
from aiocache import Cache

# Загрузка токенов из файла .env
load_dotenv("all.env")

TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')

if not TELEGRAM_API_TOKEN or not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
    raise ValueError("Отсутствуют необходимые токены и ключи в .env файле")

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Локальная временная зона
LOCAL_TIMEZONE = pytz.timezone('Europe/Moscow')

# Логирование
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("error.log"),
        logging.StreamHandler()
    ]
)

# Константы и кэш
CACHE_TIMEOUT = 10  # Время жизни кэша в секундах
SUPPORTED_SYMBOLS = set()

# Асинхронный кэш для цен криптовалют
cache = Cache(Cache.MEMORY)

# Локализация сообщений
MESSAGES = {
    "ru": {
        "start": "Привет! Чтобы узнать список команд, введите: /help",
        "help": "Список доступных команд:\n"
                 "/price <пары> - Получение текущей цены указанных пар криптовалют.\n"
                 "Пример использования:\n  /price btc/usdt\n  /price btc/usdt eth/btc ada/usdt\n"
                 "Максимум: 5 пар за один запрос.\n\n"
                 "/history <пара> - Получение исторических данных за последние 24 часа.\n"
                 "Показывает цены закрытия за каждый час.\n"
                 "Пример использования:\n  /history btc/usdt\n\n"
                 "/list - Показать список доступных базовых валют (например, USDT, BTC).\n"
                 "Пример использования:\n  /list\n\n"
                 "/help - Справка по всем доступным командам.\n"
                 "\nДополнительная информация:\n"
                 "- Используйте символы криптовалют в формате SYMBOL1/SYMBOL2, например: btc/usdt.\n"
                 "- Поддерживаются только пары, доступные на Binance.\n"
                 "- Если пара не поддерживается, бот уведомит вас.\n",
        "list": "Доступные базовые валюты:\n{currencies}",
        "price_no_args": "Укажите пару криптовалют. Пример: /price btc/usdt",
        "price_result": "{symbol}: {price:,.2f}",
        "price_cached_result": "{symbol}: {price:,.2f} (из кэша)",
        "price_api_error": "Ошибка Binance API для {symbol}. Попробуйте позже.",
        "price_not_supported": "Пара {symbol} не поддерживается Binance.",
        "price_throttle": "Подождите перед повторным запросом.",
        "history_no_args": "Укажите пару криптовалют. Пример: /history btc/usdt",
        "history_result": "Исторические данные {symbol} за последние 24 часа:\n{data}",
        "history_error": "Ошибка Binance API. Попробуйте позже."
    },
    "en": {
        "start": "Hello! To see commands, type: /help",
        "help": "List of available commands:\n"
                 "/price <pairs> - Get the current price of specified cryptocurrency pairs.\n"
                 "Example usage:\n  /price btc/usdt\n  /price btc/usdt eth/btc ada/usdt\n"
                 "Maximum: 5 pairs per request.\n\n"
                 "/history <pair> - Get historical data for the last 24 hours.\n"
                 "Displays hourly closing prices.\n"
                 "Example usage:\n  /history btc/usdt\n\n"
                 "/list - Display a list of available base currencies (e.g., USDT, BTC).\n"
                 "Example usage:\n  /list\n\n"
                 "/help - Help for all available commands.\n"
                 "\nAdditional information:\n"
                 "- Use cryptocurrency symbols in the format SYMBOL1/SYMBOL2, e.g., btc/usdt.\n"
                 "- Only pairs available on Binance are supported.\n"
                 "- If a pair is not supported, the bot will notify you.\n",
        "list": "Available base currencies:\n{currencies}",
        "price_no_args": "Specify a pair. Example: /price btc/usdt",
        "price_result": "{symbol}: {price:,.2f}",
        "price_cached_result": "{symbol}: {price:,.2f} (from cache)",
        "price_api_error": "Binance API error for {symbol}. Try later.",
        "price_not_supported": "Pair {symbol} not supported by Binance.",
        "price_throttle": "Please wait before making another request.",
        "history_no_args": "Specify a pair. Example: /history btc/usdt",
        "history_result": "Historical data {symbol} for the last 24 hours:\n{data}",
        "history_error": "Binance API error. Try later."
    }
}

# Логирование ошибок
def log_error_to_file(exception):
    local_time = datetime.now(LOCAL_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
    logging.error(f"{local_time} - {traceback.format_exc()}")

# Определение языка пользователя
def get_user_language(user):
    return user.language_code.split('-')[0] if user.language_code and user.language_code.split('-')[0] in MESSAGES else "en"

# Загрузка поддерживаемых символов Binance
async def load_supported_symbols():
    global SUPPORTED_SYMBOLS
    try:
        exchange_info = await client.get_exchange_info()
        SUPPORTED_SYMBOLS = {symbol['symbol'] for symbol in exchange_info['symbols']}
        logging.info(f"Загружено {len(SUPPORTED_SYMBOLS)} поддерживаемых символов.")
    except Exception as e:
        log_error_to_file(e)
        raise

# Проверка троттлинга
async def check_throttle(user_id):
    last_request_time = await cache.get(f"throttle_{user_id}")
    current_time = time.time()
    if last_request_time and current_time - last_request_time < CACHE_TIMEOUT:
        return False
    await cache.set(f"throttle_{user_id}", current_time, ttl=CACHE_TIMEOUT)
    return True

# Команда /start
@dp.message(Command("start"))
async def start_command(message: Message):
    lang = get_user_language(message.from_user)
    await message.reply(MESSAGES[lang]["start"])

# Команда /help
@dp.message(Command("help"))
async def help_command(message: Message):
    lang = get_user_language(message.from_user)
    await message.reply(MESSAGES[lang]["help"])

# Команда /list
@dp.message(Command("list"))
async def list_command(message: Message):
    lang = get_user_language(message.from_user)
    base_currencies = ["USDT", "BTC", "ETH", "EUR", "BNB"]
    response = MESSAGES[lang]["list"].format(currencies="\n".join(f"- {currency}" for currency in base_currencies))
    await message.reply(response)

# Команда /price
@dp.message(Command("price"))
async def price_command(message: Message):
    lang = get_user_language(message.from_user)
    args = message.text.split()
    if len(args) < 2:
        await message.reply(MESSAGES[lang]["price_no_args"])
        return

    if not await check_throttle(message.from_user.id):
        await message.reply(MESSAGES[lang]["price_throttle"])
        return

    symbols = args[1:]
    if len(symbols) > 5:
        await message.reply("Максимум 5 пар за один запрос.")
        return

    response = []
    for symbol in symbols:
        normalized_symbol = symbol.replace("/", "").upper()

        if normalized_symbol not in SUPPORTED_SYMBOLS:
            response.append(MESSAGES[lang]["price_not_supported"].format(symbol=symbol.upper()))
            continue

        cached_price = await cache.get(normalized_symbol)
        if cached_price is not None:
            response.append(MESSAGES[lang]["price_cached_result"].format(symbol=symbol.upper(), price=cached_price))
            continue

        try:
            price_data = await client.get_symbol_ticker(symbol=normalized_symbol)
            price = float(price_data['price'])
            response.append(MESSAGES[lang]["price_result"].format(symbol=symbol.upper(), price=price))
            await cache.set(normalized_symbol, price, ttl=CACHE_TIMEOUT)
        except BinanceAPIException as e:
            log_error_to_file(e)
            response.append(MESSAGES[lang]["price_api_error"].format(symbol=symbol.upper()))

    await message.reply("\n".join(response))

# Команда /history
@dp.message(Command("history"))
async def history_command(message: Message):
    lang = get_user_language(message.from_user)
    args = message.text.split()
    if len(args) != 2:
        await message.reply(MESSAGES[lang]["history_no_args"])
        return

    symbol = args[1].replace("/", "").upper()

    if symbol not in SUPPORTED_SYMBOLS:
        await message.reply(MESSAGES[lang]["price_not_supported"].format(symbol=symbol.upper()))
        return

    try:
        klines = await client.get_klines(symbol=symbol, interval="1h", limit=24)
        data = "\n".join([f"Час {i + 1}: {float(kline[4]):,.2f} USDT" if lang == "ru" else f"Hour {i + 1}: {float(kline[4]):,.2f} USDT" for i, kline in enumerate(klines)])
        response = MESSAGES[lang]["history_result"].format(symbol=symbol, data=data)
        await message.reply(response)
    except BinanceAPIException as e:
        log_error_to_file(e)
        await message.reply(MESSAGES[lang]["history_error"])

# Запуск бота
async def main():
    global client
    try:
        client = await AsyncClient.create(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        await load_supported_symbols()
        await dp.start_polling(bot)
    except Exception as e:
        log_error_to_file(e)
    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
