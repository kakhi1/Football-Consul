# Football Consul

Football Consul is an AI-powered Telegram bot and web scraper designed to analyze football statistics.

It uses Playwright and BeautifulSoup to extract match stats and lineups into a local SQLite database, and a Gemini-powered Telegram agent to translate natural language user questions into SQL queries.

---

## Features

- Automated Data Extraction  
  Scrapes match stats, xG, possession, and lineups using `playwright` and `bs4`.

- Normalized SQLite Database  
  Stores matches, teams, players, and match lineups.

- Text-to-SQL AI Agent  
  Uses Google's Gemini to parse user questions, query the local database, and return conversational, mathematically accurate insights. Now supports both **Telegram** and **Terminal** interfaces.

---

## Prerequisites

- Python 3.8+
- A Telegram Bot Token (from BotFather)
- A Google Gemini API Key

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd football-consul
```

---

### 2. Create and Activate a Virtual Environment

Mac / Linux:

```bash
python -m venv venv
source venv/bin/activate
```

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Install Playwright Browsers

This step is required for the web scraper to function.

```bash
playwright install chromium
```

---

### 5. Configure Environment Variables

Create a `.env` file in the root directory and add:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GOOGLE_API_KEY=your_gemini_api_key_here
GOOGLE_MODEL_NAME=gemini-2.5-flash
PLATFORM=telegram  # Set to 'telegram' for the bot, or 'terminal' for local CLI chat
```

You may change the model name to your preferred Gemini model if needed.

---

## Usage

### Step 1: Build the Database

Run the parser to scrape the latest football data and populate `football_consul.db`:

```bash
python main_parser.py
```

---

### Step 2: Start the AI Agent

First, ensure your `PLATFORM` variable in the `.env` file is set to your desired mode (`telegram` or `terminal`).

```bash
python app.py
```

- **If you are using Telegram (`PLATFORM=telegram`):**
  Send `/start` to your bot on Telegram and ask questions like:
  - How many goals did a team score at home this season?
  - Which team has the highest average possession?
  - Show the last 5 match results for a specific team.

- **If you are using the Terminal (`PLATFORM=terminal`):**
  Type your questions directly into the command line prompt to chat with the AI locally and view your token usage.

---

## How It Works

1. Playwright scrapes match data.
2. BeautifulSoup parses and normalizes the HTML.
3. Data is stored in a structured SQLite database.
4. Gemini converts natural language questions into SQL queries.
5. The bot executes the query and returns an intelligent response.

---

## Project Structure (Example)

```
football-consul/
│
├── main_parser.py
├── chat.py
├── database.py
├── football_consul.db
├── requirements.txt
├── .env
└── README.md
```

---

## Notes

- Always run the parser before starting the bot if you need fresh data.
- Make sure your Telegram token and Gemini API key are valid.
- The scraper depends on the target website’s HTML structure. Changes to the site may require parser updates.

---
