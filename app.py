import matplotlib.pyplot as plt
import sqlite3
import os
import logging
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import platform
import subprocess
# 1. Setup & Environment
load_dotenv()
PLATFORM = os.getenv("PLATFORM", "terminal").lower()
AI_MODEL = os.getenv("AI_MODEL", "google").lower()

# Model 1: The Conversationalist (Summarizes data and talks to the user)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
# Model 2: The Logic Engine (Strictly for analyzing queries and calling SQL tools)
SECOND_OLLAMA_MODEL = os.getenv("SECOND_OLLAMA_MODEL", "qwen2.5-coder")

# --- INITIALIZE GOOGLE CLIENT GLOBALLY SO IT DOESN'T CLOSE ---
google_client = None
if AI_MODEL != "ollama":
    from google import genai
    from google.genai import types
    google_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

if PLATFORM == "telegram":
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

# 2. Tools & Memory
agent_memory = {}


def generate_bar_chart(labels: list[str], values: list[float], title: str, ylabel: str) -> str:
    """Generates a bar chart, saves it as 'chart.png', and clears memory."""
    if PLATFORM != "telegram":
        print(f"📊 [Drawing Chart]: {title}")

    try:
        plt.figure(figsize=(8, 5))
        plt.bar(labels, values, color='#1DA1F2')
        plt.title(title)
        plt.ylabel(ylabel)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        plt.savefig('chart.png')

        # --- NEW: AUTO-OPEN CHART IN TERMINAL MODE ---
        if PLATFORM == "terminal":
            try:
                if platform.system() == 'Windows':
                    os.startfile('chart.png')
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(('open', 'chart.png'))
                else:  # Linux
                    subprocess.call(('xdg-open', 'chart.png'))
            except Exception as e:
                print(f"⚠️ Could not open image automatically: {e}")

        plt.close()
        return "SUCCESS: Chart saved as chart.png. Tell the user you have drawn the chart and provide the text breakdown."
    except Exception as e:
        return f"ERROR: Could not generate chart. {e}"


def manage_memory(action: str, data: dict) -> str:
    """Saves or retrieves important stats to/from memory to use in future SQL queries."""
    if action == 'save':
        for key, value in data.items():
            agent_memory[key] = str(value)
            if PLATFORM != "telegram":
                print(f"\n🧠 [Memory Saved]: {key} -> {value}")
        return f"Successfully saved {len(data)} items to memory."

    elif action == 'read':
        # FIX: Handle if the AI sends {"keys": ["team_a", "team_b"]} instead of a direct dict
        if 'keys' in data and isinstance(data['keys'], list):
            keys_to_read = data['keys']
        else:
            keys_to_read = data.keys()

        retrieved = {key: agent_memory.get(
            key, "Not found") for key in keys_to_read}

        for key, val in retrieved.items():
            if PLATFORM != "telegram":
                print(f"\n🧠 [Memory Accessed]: {key} -> {val}")
        return str(retrieved)

    return "Error: Action must be 'save' or 'read'."


def execute_sql_query(query: str, agent_understanding: str = "") -> str:
    """Executes a SQL query on the football_consul.db SQLite database."""
    if PLATFORM != "telegram":
        print(f"\n🤔 [Agent Thinking]: {agent_understanding}")
        print(f"🗄️ [Running SQL]: {query}")

    try:
        conn = sqlite3.connect('football_consul.db')
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        conn.close()

        # --- NEW: ANTI-HALLUCINATION LOGIC FOR MISSING DATA ---
        # If the result is completely empty, or just a tuple with a None value (like from a SUM that found nothing)
        if not result or result == [(None,)]:
            if PLATFORM != "telegram":
                print("⚠️ [Database Returned No Data]")

            empty_response = {
                "status": "SUCCESS_BUT_EMPTY",
                "message": "The SQL query was valid, but 0 rows matched the condition.",
                "INSTRUCTION": "The database does not contain this information (the team, player, or match might not be scraped yet). You MUST tell the user honestly that you do not have data for this request. DO NOT guess. DO NOT say the answer is 0."
            }
            return json.dumps(empty_response)

        # If data exists, return it normally
        return str(result)

    except Exception as e:
        if PLATFORM != "telegram":
            print(f"⚠️ [Database Error]: {e}")

        error_response = {
            "CRITICAL_FAILURE": True,
            "ERROR_MESSAGE": str(e),
            "INSTRUCTION": "The SQL query failed. You are STRICTLY FORBIDDEN from guessing the answer. You MUST correct the syntax and call the execute_sql_query tool again."
        }
        return json.dumps(error_response)


available_functions = {
    'execute_sql_query': execute_sql_query,
    'manage_memory': manage_memory,
    'generate_bar_chart': generate_bar_chart,
}

# 3. System Instructions & Schemas
system_instruction = """
You are 'Football Consul', an expert AI football data analyst.
You have access to a tool called `execute_sql_query`. Use it to query the SQLite database to answer user questions.

DATABASE SCHEMA:

Table: `match_stats`
Columns: 
- match_id (TEXT)
- match_date (TEXT, Format: YYYY-MM-DD HH:MM)
- competition (TEXT, e.g., 'LaLiga', 'Champions League', 'Premier League')
- match_stage (TEXT, e.g., 'Regular Season', 'Quarter-finals', 'Group Stage')
- home_team (TEXT)
- away_team (TEXT)
- home_score (INTEGER)
- away_score (INTEGER)
- home_formation (TEXT)
- away_formation (TEXT)
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
- home_offsides (INTEGER)
- away_offsides (INTEGER)
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

Table: `players`
Columns: 
- player_id (TEXT)
- name (TEXT)

Table: `match_lineups`
Columns: 
- lineup_id (INTEGER)
- match_id (TEXT, Foreign Key to match_stats)
- player_id (TEXT, Foreign Key to players)
- team_type (TEXT, 'Home' or 'Away')
- shirt_number (TEXT)
- is_starter (BOOLEAN)
- rating (REAL)

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
8. MEMORY USAGE (CRITICAL EXECUTION ORDER):
   You have access to a `manage_memory` tool. You must follow this exact sequence:
   - STEP 1 (Calculate): When asked for a baseline stat or average, use `execute_sql_query`.
   - STEP 2 (Save): BEFORE replying to the user, you MUST immediately use `manage_memory` with action='save' to store the exact numerical result (e.g., key: 'everton_avg_corners', value: '5.43'). Do not skip this step.
   - STEP 3 (Reply): Present the answer to the user.
   - STEP 4 (Recall): If the user asks a follow-up question requiring past stats, use `manage_memory` with action='read' to retrieve the exact value BEFORE writing your next SQL query.
9. UNDERSTANDING FIRST: When using the `execute_sql_query` tool, you MUST fill out the `agent_understanding` parameter. Briefly explain who the subject is and exactly which columns you are targeting before writing the SQL.
10. TEMPORAL DATA: Use the `match_date` column for questions about a team's 'last match' or 'recent games'. Example: `ORDER BY match_date DESC LIMIT 5`.
11. COMPETITIONS & STAGES: Use `competition` and `match_stage` to filter for specific tournaments or knockout rounds (e.g., `WHERE competition = 'Champions League' AND match_stage != 'Group Stage'`).
12. ERROR HANDLING: If your tool returns a string starting with "SQL Error", you made a syntax mistake. Do not tell the user there is an error; immediately execute a new, corrected SQL query.
13. TIME-RESTRICTED AGGREGATIONS (The "Last N Games" Pattern):
    When a user asks for a total or average over a specific number of recent games, you MUST respect SQL order of operations. You cannot aggregate and LIMIT in the same query level.
    Use this exact architectural pattern with a CASE statement inside a subquery:
    SELECT SUM(target_stat) FROM (
        SELECT CASE WHEN home_team LIKE '%[TEAM]%' THEN home_stat ELSE away_stat END AS target_stat
        FROM match_stats 
        WHERE (home_team LIKE '%[TEAM]%' OR away_team LIKE '%[TEAM]%')
        ORDER BY match_date DESC LIMIT [N]
    )

14. STRICT SCHEMA AND ERROR RECOVERY:
    - You must ONLY use the exact column names listed in the schema. Do not invent columns (e.g., use `home_team`, never `hoome_team`).
    - If the `execute_sql_query` tool returns a JSON error with "CRITICAL_FAILURE", you have made a typo. You are FORBIDDEN from guessing the final answer. You must immediately write a new, corrected SQL query and run the tool again.
15. MISSING DATA AND HONESTY (ANTI-HALLUCINATION):
    If the user asks about a team, player, or league that is not in the database, the `execute_sql_query` tool will return a JSON with "SUCCESS_BUT_EMPTY". 
    - You are STRICTLY FORBIDDEN from guessing a number or assuming the answer is 0.
    - 0 means they played and scored no goals. Empty means we have no record of them playing. Do not confuse the two.
    - You MUST reply to the user stating clearly: "I apologize, but I don't currently have data for that specific team/player/match in my database."
16. DRAWING CHARTS: If the user explicitly asks for a chart or graph, follow these steps:
    - Step 1: Use `execute_sql_query` to get the raw data.
    - Step 2: Use the `generate_bar_chart` tool, passing the extracted names as `labels` and the numbers as `values`.
    - Step 3: You MUST output a final conversational text response containing the actual numbers. Never end your turn with just a tool call.
"""

ollama_tools = [
    {
        'type': 'function',
        'function': {
            'name': 'execute_sql_query',
            'description': 'Executes a SQL query on the SQLite database.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': 'The SQL query to run.'},
                    'agent_understanding': {'type': 'string', 'description': 'A 1-sentence explanation of what you think the user wants.'}
                },
                'required': ['query', 'agent_understanding']
            }
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'manage_memory',
            'description': 'Saves or retrieves stats to/from memory.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['save', 'read']},
                    'data': {'type': 'object', 'description': 'Dictionary of key-value pairs.'}
                },
                'required': ['action', 'data']
            }
        }
    }
]

# --- 4. OLLAMA MULTI-MODEL WRAPPER ---


class OllamaMultiModelSession:
    """Handles standard conversation with Model 1, and delegates Tool/SQL execution to Model 2."""

    def __init__(self, system_prompt, chat_model, logic_model):
        import ollama
        self.ollama = ollama
        self.chat_model = chat_model
        self.logic_model = logic_model
        self.messages = [{'role': 'system', 'content': system_prompt}]

    class MockResponse:
        def __init__(self, text):
            self.text = text

    def send_message_sync(self, text):
        self.messages.append({'role': 'user', 'content': text})

        max_retries = 3
        attempts = 0

        while attempts < max_retries:
            if PLATFORM != "telegram":
                print(
                    f"⚙️ [Routing to {self.logic_model} for logic analysis (Attempt {attempts + 1})...]")

            logic_response = self.ollama.chat(
                model=self.logic_model,
                messages=self.messages,
                tools=ollama_tools
            )

            logic_message = logic_response['message']
            self.messages.append(logic_message)

            tool_calls_to_execute = logic_message.get('tool_calls', [])

            # --- JSON FALLBACK PARSER ---
            if not tool_calls_to_execute and logic_message.get('content'):
                try:
                    parsed_content = json.loads(
                        logic_message['content'].strip())
                    if isinstance(parsed_content, dict) and "name" in parsed_content and "arguments" in parsed_content:
                        tool_calls_to_execute = [{'function': parsed_content}]
                except json.JSONDecodeError:
                    pass

            if not tool_calls_to_execute:
                return self.MockResponse(logic_message['content'])

            # STEP 2: Execute the tools
            has_error = False
            for tool in tool_calls_to_execute:
                func_name = tool['function']['name']
                func_args = tool['function']['arguments']

                if func_name in available_functions:
                    function_to_call = available_functions[func_name]
                    try:
                        if isinstance(func_args, str):
                            func_args = json.loads(func_args)
                        function_response = function_to_call(**func_args)
                    except Exception as e:
                        function_response = f"SQL Error: {e}"

                    self.messages.append({
                        'role': 'tool',
                        'content': str(function_response),
                        'name': func_name
                    })

                    # Check if the tool returned an error string
                    if str(function_response).startswith("SQL Error"):
                        has_error = True

            # If there was an SQL error, loop back and let the Logic Engine try again
            if has_error:
                attempts += 1
                if PLATFORM != "telegram":
                    print(
                        "⚠️ [SQL Error detected. Asking Logic Engine to correct it...]")
                continue  # Go back to the top of the while loop
            else:
                break  # Success! Break out of the loop and go to the Chat Model

        # STEP 3: Pass the successful history to the Chat Model
        if PLATFORM != "telegram":
            print(f"🗣️ [Routing to {self.chat_model} to generate response...]")

        chat_response = self.ollama.chat(
            model=self.chat_model,
            messages=self.messages
        )

        final_message = chat_response['message']
        self.messages.append(final_message)

        return self.MockResponse(final_message['content'])


def create_chat_session():
    """Factory to create either a Google or Ollama chat session."""
    if AI_MODEL == "ollama":
        if PLATFORM != "telegram":
            print(
                f"🔧 Using Ollama Pipeline | Logic: {SECOND_OLLAMA_MODEL} | Chat: {OLLAMA_MODEL}")
        return OllamaMultiModelSession(system_instruction, OLLAMA_MODEL, SECOND_OLLAMA_MODEL)
    else:
        if PLATFORM != "telegram":
            print("☁️ Using Google Gemini")
        # Use the global client here!
        return google_client.chats.create(
            model=os.getenv("GOOGLE_MODEL_NAME"),
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[execute_sql_query, manage_memory,
                       generate_bar_chart],  # <--- Added it here!
                temperature=0.0,
            )
        )


# --- 5. TELEGRAM LOGIC ---
user_chats = {}


def get_or_create_chat(chat_id):
    if chat_id not in user_chats:
        user_chats[chat_id] = create_chat_session()
    return user_chats[chat_id]


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    chat_id = update.message.chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    try:
        chat_session = get_or_create_chat(chat_id)

        if AI_MODEL == "ollama":
            response = chat_session.send_message_sync(user_input)
        else:
            response = chat_session.send_message(user_input)

        # --- NEW: COMBINED TELEGRAM OUTPUT LOGIC ---
        if os.path.exists('chart.png'):
            await context.bot.send_chat_action(chat_id=chat_id, action='upload_photo')
            with open('chart.png', 'rb') as photo:

                # Telegram captions have a maximum limit of ~1024 characters.
                # If the AI wrote a short text, bundle them together!
                if len(response.text) < 1000:
                    await update.message.reply_photo(photo=photo, caption=response.text)
                else:
                    # If the AI wrote a massive essay, send them separately so it doesn't crash
                    await update.message.reply_photo(photo=photo)
                    await update.message.reply_text(response.text)

            # Delete the file to save memory
            os.remove('chart.png')
        else:
            # No chart was generated, just send the normal text
            await update.message.reply_text(response.text)

    except Exception as e:
        error_msg = f"⚠️ Oops, I hit an error: {e}"
        print(error_msg)
        await update.message.reply_text(error_msg)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽ Football Consul is ready! Send me a message to analyze some stats.")


def run_telegram_bot():
    print("🤖 Starting Telegram Bot Mode...")
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message))
    print("⚽ Bot is polling for messages! Press Ctrl+C to stop.")
    app.run_polling()

# --- 6. TERMINAL LOGIC ---


def run_terminal_chat():
    print("🤖 Starting Terminal Mode...")
    chat = create_chat_session()
    print("⚽ Football Consul is ready! Type 'exit' to close.")
    print("-" * 50)

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']:
            break

        try:
            if AI_MODEL == "ollama":
                response = chat.send_message_sync(user_input)
            else:
                response = chat.send_message(user_input)

            text_output = response.text if response.text else "Here is your chart!"
            print(f"\n⚽ Football Consul: {text_output}")
        except Exception as e:
            print(f"\n⚠️ Oops, I hit an error: {e}")


# --- 7. MAIN EXECUTION ROUTER ---
if __name__ == '__main__':
    if PLATFORM == "telegram":
        run_telegram_bot()
    else:
        run_terminal_chat()
