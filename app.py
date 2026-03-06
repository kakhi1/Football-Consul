import sqlite3
import os
import logging
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

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


def manage_memory(action: str, data: dict) -> str:
    """Saves or retrieves important stats to/from memory to use in future SQL queries."""
    if action == 'save':
        for key, value in data.items():
            agent_memory[key] = str(value)
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
        return str(result)
    except Exception as e:
        return f"SQL Error: {e}"


available_functions = {
    'execute_sql_query': execute_sql_query,
    'manage_memory': manage_memory,
}

# 3. System Instructions & Schemas
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

        # STEP 1: Ask the Logic Model (SECOND_OLLAMA_MODEL) if a tool/SQL is needed
        if PLATFORM != "telegram":
            print(f"⚙️ [Routing to {self.logic_model} for logic analysis...]")

        logic_response = self.ollama.chat(
            model=self.logic_model,
            messages=self.messages,
            tools=ollama_tools
        )

        logic_message = logic_response['message']
        self.messages.append(logic_message)

        # Grab official tool calls if the model used the API correctly
        tool_calls_to_execute = logic_message.get('tool_calls', [])

        # --- JSON FALLBACK PARSER ---
        # If no official tools were triggered, check if the model just printed raw JSON text
        if not tool_calls_to_execute and logic_message.get('content'):
            try:
                # Try to load the text as JSON
                parsed_content = json.loads(logic_message['content'].strip())
                # Check if it looks like our tool format
                if isinstance(parsed_content, dict) and "name" in parsed_content and "arguments" in parsed_content:
                    if PLATFORM != "telegram":
                        print(
                            "🔧 [Caught raw JSON text and converting it to a tool call...]")
                    tool_calls_to_execute = [{'function': parsed_content}]
            except json.JSONDecodeError:
                pass  # It's just normal text, move on

        # If STILL no tools to execute, return the text directly to the user
        if not tool_calls_to_execute:
            return self.MockResponse(logic_message['content'])

        # STEP 2: Execute the tools
        for tool in tool_calls_to_execute:
            func_name = tool['function']['name']
            func_args = tool['function']['arguments']

            if func_name in available_functions:
                function_to_call = available_functions[func_name]
                try:
                    # Convert string args to dict if the model messed up formatting
                    if isinstance(func_args, str):
                        func_args = json.loads(func_args)
                    function_response = function_to_call(**func_args)
                except Exception as e:
                    function_response = f"Error executing tool: {e}"

                # Append the raw database result to the history
                self.messages.append({
                    'role': 'tool',
                    'content': str(function_response),
                    'name': func_name
                })

        # STEP 3: Pass the history (now containing the raw SQL data) to the Chat Model (OLLAMA_MODEL)
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
                tools=[execute_sql_query, manage_memory],
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

            print(f"\n⚽ Football Consul: {response.text}")
            print("-" * 50)

        except Exception as e:
            print(f"\n⚠️ Oops, I hit an error: {e}")


# --- 7. MAIN EXECUTION ROUTER ---
if __name__ == '__main__':
    if PLATFORM == "telegram":
        run_telegram_bot()
    else:
        run_terminal_chat()
