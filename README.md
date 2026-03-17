# Football Consul

Football Consul is an AI-powered Telegram bot and analytics engine designed to analyze football statistics.

It uses Playwright and BeautifulSoup to extract match stats and lineups into a local SQLite database. It features an AI agent that translates natural language into complex SQL queries, supporting both Google Gemini and local Ollama models.

---

## 🚀 Key Features

- **📊 Dynamic Data Visualization:** Automatically generates bar charts using `matplotlib` to visualize trends (e.g., shots over the last 5 games).
- **🛡️ Anti-Hallucination Engine:** The bot is strictly forbidden from guessing. If data is missing or a query is invalid, it uses a self-correction loop or honestly informs the user that data is unavailable.
- **🧠 Advanced SQL Logic & Memory:** Handles complex "Last N Games" queries and player-specific joins. It saves baseline stats to memory to answer follow-up questions accurately.
- **📱 Unified Telegram Output:** Delivers charts and text breakdowns as a single, combined message (Photo + Caption) for a cleaner experience.
- **🪟 Terminal Auto-Open:** Charts automatically pop open in your default Windows photo viewer when running in Terminal mode.
- **🕷️ Automated Data Extraction:** Scrapes match stats, xG, possession, and lineups using `playwright` and `bs4`.
- **🗄️ Normalized SQLite Database:** Stores matches, teams, players, and match lineups efficiently.

---

## Prerequisites

- Python 3.8+
- A Telegram Bot Token (from BotFather)
- A Google Gemini API Key
- _Optional:_ [Ollama](https://ollama.com/) installed locally (if you plan to use local models)

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
AI_MODEL=google           # Set to 'google' for Gemini, or 'ollama' for local models

# Ollama Configuration (Used if AI_MODEL=ollama)
OLLAMA_MODEL=llama3.1               # The conversational model
SECOND_OLLAMA_MODEL=qwen2.5-coder   # The logic/SQL engine model
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

## Example Usage (Terminal Mode)

When running the bot in the terminal (`PLATFORM=terminal`), you can see exactly how the AI translates your natural language into SQL queries, executes them against the database, and returns the results.

Here is an example of a session analyzing team stats:

```text
🤖 Starting Terminal Mode...
☁️ Using Google Gemini
⚽ Football Consul is ready! Type 'exit' to close.
--------------------------------------------------

You: show ossasuna avarage fouls and corners

🤔 [Agent Thinking]: The user is asking for the average fouls and corners for Osasuna. I need to query the match_stats table, combining home and away stats for Osasuna using UNION ALL to calculate the average fouls and corners.
🗄️ [Running SQL]:
SELECT
  AVG(team_fouls) AS average_fouls,
  AVG(team_corners) AS average_corners
FROM (
  SELECT home_fouls AS team_fouls, home_corners AS team_corners FROM match_stats WHERE home_team LIKE '%Osasuna%'
  UNION ALL
  SELECT away_fouls AS team_fouls, away_corners AS team_corners FROM match_stats WHERE away_team LIKE '%Osasuna%'
);

🧠 [Memory Saved]: osasuna_average_fouls -> 13.538
🧠 [Memory Saved]: osasuna_average_corners -> 3.192

⚽ Football Consul: Osasuna averages approximately 13.54 fouls and 3.19 corners per match.
--------------------------------------------------

You: when ossasuna plays at home, show all teams, what have avarage corners less 3.5

🤔 [Agent Thinking]: The user wants to see which teams, when playing away against Osasuna at home, had an average of less than 3.5 corners. I need to filter for Osasuna as the home team, group by the away team, and then filter those groups where the average away corners is less than 3.5.
🗄️ [Running SQL]:
SELECT
  away_team AS opponent_team,
  AVG(away_corners) AS average_opponent_corners
FROM match_stats
WHERE home_team LIKE '%Osasuna%'
GROUP BY away_team
HAVING AVG(away_corners) < 3.5;

⚽ Football Consul: When Osasuna plays at home, the following teams had an average of less than 3.5 corners:
* Alaves: 0.0 corners
* Celta Vigo: 2.0 corners
* Elche: 3.0 corners
* Levante: 3.0 corners
* Real Sociedad: 3.0 corners
* Villarreal: 2.0 corners
--------------------------------------------------
```

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
