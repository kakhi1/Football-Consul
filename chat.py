import sqlite3
import os
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 1. Setup Logging (Helps with debugging Telegram issues)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 2. Set your API Keys
load_dotenv()

# 3. Define the Tool


def execute_sql_query(query: str) -> str:
    """Executes a SQL query on the football_consul.db SQLite database and returns the result."""
    print(f"\n[Football Consul is running SQL]: {query}")
    try:
        conn = sqlite3.connect('football_consul.db')
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        conn.close()
        return str(result)
    except Exception as e:
        return f"SQL Error: {e}"


# 4. Initialize the GenAI Client
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# 5. System Instructions
system_instruction = """
You are 'Football Consul', an expert AI football data analyst.
You have access to a tool called `execute_sql_query`. Use it to query the SQLite database to answer user questions.

DATABASE SCHEMA:
Table name: `match_stats`
Columns: 
- match_id (TEXT)
- home_team (TEXT)
- away_team (TEXT)
- home_score (INTEGER)
- away_score (INTEGER)
- home_xg (REAL)
- away_xg (REAL)
- home_possession_pct (INTEGER)
- away_possession_pct (INTEGER)
- home_total_shots (INTEGER)
- away_total_shots (INTEGER)
- home_shots_on_target (INTEGER)
- away_shots_on_target (INTEGER)
- home_corners (INTEGER)
- away_corners (INTEGER)

CRITICAL RULES:
1. Always use the `LIKE` operator with wildcards for team names (e.g., `WHERE home_team LIKE '%Villa%'`).
2. Teams play both HOME and AWAY. If calculating a total or average for a team across all matches, you MUST combine their home and away stats using UNION ALL.
3. If the user specifies "when they are home", only query the home columns.
4. "Spurs" = "Tottenham", "United" = "Manchester Utd".
5. Run the query, get the exact mathematical result, and explain it conversationally. Do not expose the raw SQL to the user in your final answer.
6. Unified Team Perspective: A team's data is split across home and away columns. Whenever calculating a team's stats, you MUST standardize the perspective using a UNION ALL subquery. 
   - When the target team is the 'home_team', alias them as 'target_team', their opponent as 'opponent_team', their stats as 'team_stat' vs 'opponent_stat', AND add a column `'Home' AS venue`.
   - Do the exact reverse when the target team is the 'away_team' AND add a column `'Away' AS venue`.
7. Head-to-Head vs Overall Average: If a user asks against which teams a club performed "better/worse than their average", you MUST follow these exact steps:
   - Step 1: Calculate their overall season average using a CTE.
   - Step 2: Build the Unified Team Perspective subquery (from Rule 6), ensuring the 'venue' column is included.
   - Step 3: GROUP BY opponent_team AND venue on that unified subquery.
   - Step 4: Use a HAVING clause to compare the venue-specific head-to-head average against the overall average CTE.
"""

# Dictionary to hold individual chat sessions for different Telegram users
user_chats = {}


def get_or_create_chat(chat_id):
    """Retrieves an existing chat session for a user or creates a new one."""
    if chat_id not in user_chats:
        # We use client.aio for asynchronous requests to prevent bot freezing
        user_chats[chat_id] = client.aio.chats.create(
            model=os.getenv("GOOGLE_MODEL_NAME"),
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[execute_sql_query],
                temperature=0.0,
            )
        )
    return user_chats[chat_id]

# 6. Telegram Bot Handlers


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    await update.message.reply_text("⚽ Football Consul is ready! Send me a message to analyze some stats.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages."""
    user_input = update.message.text
    chat_id = update.message.chat_id

    # Show the "typing..." indicator in Telegram
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    try:
        # Get the specific chat history for this user
        chat_session = get_or_create_chat(chat_id)

        # Send message asynchronously
        response = await chat_session.send_message(user_input)

        # Format the response with token usage
        usage = response.usage_metadata
        reply_text = f"{response.text}\n\n📊 [Tokens] Prompt: {usage.prompt_token_count} | Response: {usage.candidates_token_count} | Total: {usage.total_token_count}"

        await update.message.reply_text(reply_text)

    except Exception as e:
        error_msg = f"⚠️ Oops, I hit an error: {e}"
        print(error_msg)
        await update.message.reply_text(error_msg)

# 7. Main Application Loop
if __name__ == '__main__':
    print("🤖 Starting Telegram Bot...")

    # Build the Telegram application
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot
    print("⚽ Bot is polling for messages! Press Ctrl+C to stop.")
    app.run_polling()
