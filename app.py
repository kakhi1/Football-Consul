import sqlite3
import os
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 1. Setup & Environment
load_dotenv()
PLATFORM = os.getenv("PLATFORM", "terminal").lower()

# Only enable basic Telegram logging if we are in Telegram mode to avoid terminal clutter
if PLATFORM == "telegram":
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

# 2. Tools & Memory (From chat_old.py)
agent_memory = {}


def manage_memory(action: str, data: dict[str, str]) -> str:
    """
    Saves or retrieves important stats to/from memory to use in future SQL queries.
    Args:
        action: 'save' or 'read'
        data: A dictionary of key-value pairs. 
              For 'save': {'aston_villa_avg_corners': '5.4', 'chelsea_avg_goals': '2.1'}
              For 'read': {'aston_villa_avg_corners': '', 'chelsea_avg_goals': ''}
    """
    if action == 'save':
        for key, value in data.items():
            agent_memory[key] = str(value)
            # Hide prints in Telegram mode
            if PLATFORM != "telegram":
                print(f"\n🧠 [Memory Saved]: {key} -> {value}")
        return f"Successfully saved {len(data)} items to memory."

    elif action == 'read':
        retrieved = {key: agent_memory.get(
            key, "Not found") for key in data.keys()}
        for key, val in retrieved.items():
            if PLATFORM != "telegram":
                print(f"\n🧠 [Memory Accessed]: {key} -> {val}")
        return str(retrieved)

    return "Error: Action must be 'save' or 'read'."


def execute_sql_query(query: str, agent_understanding: str = "") -> str:
    """
    Executes a SQL query on the football_consul.db SQLite database.
    Args:
        query: The SQL query to run.
        agent_understanding: A mandatory 1-sentence explanation of what you think the user wants, explicitly stating which columns (e.g., home vs away) you need to use.
    """
    # Hide prints in Telegram mode
    if PLATFORM != "telegram":
        print(f"\n🤔 [Agent Thinking]: {agent_understanding}")
        print(f"🗄️ [Running SQL]: {query}")

    try:
        conn = sqlite3.connect('football_consul.db')
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        conn.close()
        return str(result)
    except Exception as e:
        return f"SQL Error: {e}"


# 3. Initialize the GenAI Client & System Instructions
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

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
- home_fouls (INTEGER)
- away_fouls (INTEGER)
- away_offsides (INTEGER)
- home_offsides (INTEGER)
- home_blocked_shots (INTEGER)
- away_blocked_shots (INTEGER)
- home_yellow_cards (INTEGER)
- away_yellow_cards (INTEGER)
- home_big_chances (INTEGER)
- away_big_chances (INTEGER)
- home_passes_pct (INTEGER)
- away_passes_pct (INTEGER)
- home_goalkeeper_saves (INTEGER)
- away_goalkeeper_saves (INTEGER)

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
   - Example Output format: "Wolves (Home): 9 corners", "Wolves (Away): 8 corners".
8. MEMORY USAGE (CRITICAL EXECUTION ORDER):
   You have access to a `manage_memory` tool. You must follow this exact sequence:
   - STEP 1 (Calculate): When asked for a baseline stat or average, use `execute_sql_query`.
   - STEP 2 (Save): BEFORE replying to the user, you MUST immediately use `manage_memory` with action='save' to store the exact numerical result (e.g., key: 'everton_avg_corners', value: '5.43'). Do not skip this step.
   - STEP 3 (Reply): Present the answer to the user.
   - STEP 4 (Recall): If the user asks a follow-up question requiring past stats, use `manage_memory` with action='read' to retrieve the exact value BEFORE writing your next SQL query.
9. UNDERSTANDING FIRST: When using the `execute_sql_query` tool, you MUST fill out the `agent_understanding` parameter. Briefly explain who the subject is and exactly which columns you are targeting before writing the SQL.
"""

# Define the tools list to be injected into the chat configurations
tools_list = [execute_sql_query, manage_memory]

# --- 4. TELEGRAM LOGIC ---
user_chats = {}


def get_or_create_chat(chat_id):
    """Retrieves an existing chat session for a user or creates a new one (Async)."""
    if chat_id not in user_chats:
        user_chats[chat_id] = client.aio.chats.create(
            model=os.getenv("GOOGLE_MODEL_NAME"),
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools_list,
                temperature=0.0,
            )
        )
    return user_chats[chat_id]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    await update.message.reply_text("⚽ Football Consul is ready! Send me a message to analyze some stats.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages for Telegram."""
    user_input = update.message.text
    chat_id = update.message.chat_id

    # Show the "typing..." indicator in Telegram
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    try:
        chat_session = get_or_create_chat(chat_id)
        response = await chat_session.send_message(user_input)

        # Send ONLY the response text to Telegram (no token usage)
        await update.message.reply_text(response.text)

    except Exception as e:
        error_msg = f"⚠️ Oops, I hit an error: {e}"
        print(error_msg)
        await update.message.reply_text(error_msg)


def run_telegram_bot():
    print("🤖 Starting Telegram Bot Mode...")
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message))
    print("⚽ Bot is polling for messages! Press Ctrl+C to stop.")
    app.run_polling()


# --- 5. TERMINAL LOGIC ---
def run_terminal_chat():
    print("🤖 Starting Terminal Mode...")
    # Use standard synchronous client for the terminal loop
    chat = client.chats.create(
        model=os.getenv("GOOGLE_MODEL_NAME"),
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools_list,
            temperature=0.0,
        )
    )

    print("⚽ Football Consul (Native) is ready! Type 'exit' to close.")
    print("-" * 50)

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']:
            break

        try:
            response = chat.send_message(user_input)
            print(f"\n⚽ Football Consul: {response.text}")

            # Print token usage in terminal only
            usage = response.usage_metadata
            print(
                f"\n📊 [Token Usage] Prompt: {usage.prompt_token_count} | Response: {usage.candidates_token_count} | Total: {usage.total_token_count}")
            print("-" * 50)

        except Exception as e:
            print(f"\n⚠️ Oops, I hit an error: {e}")


# --- 6. MAIN EXECUTION ROUTER ---
if __name__ == '__main__':
    if PLATFORM == "telegram":
        run_telegram_bot()
    else:
        run_terminal_chat()
