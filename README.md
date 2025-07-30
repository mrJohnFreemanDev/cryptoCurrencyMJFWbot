# 📈 cryptoCurrencyMJFWbot

A Telegram bot that provides real-time cryptocurrency prices and 24-hour historical data using the Binance API.

## 🧩 Features

- `/price BTC/USDT ETH/BTC` — get current prices (up to 5 pairs)
- `/history BTC/USDT` — hourly closing prices for the last 24 hours
- `/list` — show available base currencies (USDT, BTC, ETH, etc.)
- Caching with aiocache to reduce API requests
- Multilingual support (🇷🇺 Russian / 🇬🇧 English)
- Anti-spam throttling per user
- Logs errors to `error.log`

## ⚙️ Tech Stack

- Python 3.10+
- Aiogram
- Binance API (AsyncClient)
- aiocache
- dotenv
- Logging with rotation and timestamp
- Hosted locally or on VPS

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/cryptoCurrencyMJFWbot.git
cd cryptoCurrencyMJFWbot
```

### 2. Create `.env` file

```env
TELEGRAM_API_TOKEN=your_telegram_token
BINANCE_API_KEY=your_binance_key
BINANCE_SECRET_KEY=your_binance_secret
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the bot

```bash
python cryptoCurrencyMJFWbot.py
```

## 🧪 Usage Example

Send the following message to your bot:

```plaintext
/price btc/usdt eth/btc
/history eth/usdt
```

And receive real-time or hourly price updates directly in Telegram.

## 📬 Contact

- Telegram: [@ivan_mudriakov](https://t.me/ivan_mudriakov)
- Email: [mr.john.freeman.works.rus@gmail.com](mailto:mr.john.freeman.works.rus@gmail.com)

---

⚡ Created with ❤️ by Ivan Mudriakov — open to collaboration and freelance work.
