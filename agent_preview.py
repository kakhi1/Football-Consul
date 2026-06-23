import os
import psycopg2
import psycopg2.extras
from typing import TypedDict, Optional
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import socket

# Force IPv4 for neon db to avoid 'Cannot assign requested address'
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

# Load environment variables
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

# Define the State
class AgentState(TypedDict):
    home_team: Optional[str]
    away_team: Optional[str]
    match_time: Optional[str]
    home_stats: Optional[dict]
    away_stats: Optional[dict]
    home_top_players: Optional[list]
    away_top_players: Optional[list]
    data_insights: Optional[str]
    preview: Optional[str]
    error: Optional[str]

# Node 1: Fetch next match from Flashscore
def fetch_next_match(state: AgentState):
    print("--- FETCHING NEXT MATCH ---")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://www.flashscore.com/football/world/world-championship/fixtures/", wait_until='domcontentloaded')
            
            page.wait_for_selector('.event__match', timeout=10000)
            match = page.locator('.event__match').first
            
            if not match.is_visible():
                browser.close()
                return {"error": "No matches visible on the page."}
                
            time_text = match.locator('.event__time').inner_text()
            home = match.locator('.event__homeParticipant').inner_text()
            away = match.locator('.event__awayParticipant').inner_text()
            
            browser.close()
            
            return {
                "home_team": home.strip(),
                "away_team": away.strip(),
                "match_time": time_text.strip()
            }
    except Exception as e:
        return {"error": f"Failed to fetch match: {str(e)}"}

# Node 2: Gather MAX stats from Database
def gather_team_stats(state: AgentState):
    print("--- GATHERING TEAM STATS ---")
    if state.get("error"):
        return state
        
    home_team = state["home_team"]
    away_team = state["away_team"]
    
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Function to fetch recent stats for a team
        def get_team_avg_stats(team_name):
            query = "SELECT * FROM world_cup_match_stats WHERE home_team = %s OR away_team = %s"
            cursor.execute(query, (team_name, team_name))
            rows = cursor.fetchall()
            
            if not rows:
                return None
                
            totals = {}
            count = {}
            
            for row in rows:
                is_home = (row['home_team'] == team_name)
                prefix = 'home_' if is_home else 'away_'
                
                score_key = 'home_score' if is_home else 'away_score'
                if row[score_key] is not None:
                    totals['goals'] = totals.get('goals', 0) + row[score_key]
                    count['goals'] = count.get('goals', 0) + 1
                    
                for key in row.keys():
                    if key.startswith(prefix) and key not in [prefix + 'team', prefix + 'formation', prefix + 'score']:
                        stat_name = key.replace(prefix, '')
                        val = row[key]
                        if val is not None and isinstance(val, (int, float)):
                            totals[stat_name] = totals.get(stat_name, 0) + val
                            count[stat_name] = count.get(stat_name, 0) + 1
                            
            avgs = {}
            for k, v in totals.items():
                if count[k] > 0:
                    avgs[f"avg_{k}"] = round(v / count[k], 2)
            return avgs if avgs else None

        # Function to fetch top players by rating
        def get_top_players(team_name):
            query = """
            SELECT p.name, ROUND(AVG(l.rating)::numeric, 2) as avg_rating, COUNT(l.match_id) as games_played
            FROM world_cup_match_lineups l
            JOIN players p ON l.player_id = p.player_id
            JOIN world_cup_match_stats s ON l.match_id = s.match_id
            WHERE (s.home_team = %s AND l.team_type = 'home') 
               OR (s.away_team = %s AND l.team_type = 'away')
            GROUP BY p.name
            HAVING AVG(l.rating) IS NOT NULL
            ORDER BY avg_rating DESC
            LIMIT 10
            """
            cursor.execute(query, (team_name, team_name))
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows else []

        home_stats = get_team_avg_stats(home_team) or {"info": "No historical data found"}
        away_stats = get_team_avg_stats(away_team) or {"info": "No historical data found"}
        
        home_players = get_top_players(home_team)
        away_players = get_top_players(away_team)
        
        conn.close()
        
        return {
            "home_stats": home_stats,
            "away_stats": away_stats,
            "home_top_players": home_players,
            "away_top_players": away_players
        }
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

# Node 3: Data Analyst Agent (Synthesizes Data)
def analyze_data(state: AgentState):
    print("--- ANALYZING DATA (DATA ANALYST AGENT) ---")
    if state.get("error"):
        return state
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.4)
    
    system_msg = SystemMessage(content="You are a brilliant Football Data Analyst. Your job is to take raw, massive JSON statistics and player ratings, and synthesize them into 5-7 crucial, high-level tactical insights and key player highlights. Focus on the most extreme numbers, tactical styles (possession vs counter), and star players.")
    
    prompt = f"""
    Upcoming Match: {state['home_team']} vs {state['away_team']}
    
    RAW DATA FOR {state['home_team']}:
    Stats: {state['home_stats']}
    Top Rated Players: {state['home_top_players']}
    
    RAW DATA FOR {state['away_team']}:
    Stats: {state['away_stats']}
    Top Rated Players: {state['away_top_players']}
    
    Please provide a concise but deep bulleted list of the "Key Tactical & Player Insights" that will decide this match.
    """
    
    response = llm.invoke([system_msg, HumanMessage(content=prompt)])
    
    return {"data_insights": response.content}

# Node 4: Preview Agent (Writes the Narrative)
def generate_preview(state: AgentState):
    print("--- GENERATING PREVIEW (PREVIEW AGENT) ---")
    if state.get("error"):
        return state
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
    
    system_msg = SystemMessage(content="You are an expert football journalist and pundit. Your task is to write a detailed, engaging, narrative-driven preview for an upcoming match. You will be provided with 'Key Tactical & Player Insights' from our Data Analyst. Build your preview around these insights, mentioning key players and statistical trends to create an exciting read.")
    
    prompt = f"""
    Upcoming Match: {state['home_team']} vs {state['away_team']}
    Date/Time: {state['match_time']}
    
    DATA ANALYST INSIGHTS:
    {state['data_insights']}
    
    Write the official Match Preview.
    """
    
    response = llm.invoke([system_msg, HumanMessage(content=prompt)])
    
    return {"preview": response.content}

# Node 5: Save Preview to Database
def save_preview_to_db(state: AgentState):
    print("--- SAVING PREVIEW TO DATABASE ---")
    if state.get("error"):
        return state
        
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        query = """
        INSERT INTO agent_previews (home_team, away_team, match_time, data_insights, preview_text)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            state['home_team'], 
            state['away_team'], 
            state['match_time'], 
            state['data_insights'], 
            state['preview']
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to save preview: {e}")
        # Not returning error to state to avoid failing the final output, just logging it
        
    return state

# Conditional edges
def check_for_errors(state: AgentState):
    if state.get("error"):
        return END
    return "gather_team_stats"

def check_for_errors_stats(state: AgentState):
    if state.get("error"):
        return END
    return "analyze_data"

def check_for_errors_analysis(state: AgentState):
    if state.get("error"):
        return END
    return "generate_preview"

def check_for_errors_preview(state: AgentState):
    if state.get("error"):
        return END
    return "save_preview_to_db"

# Build the Graph
workflow = StateGraph(AgentState)

workflow.add_node("fetch_next_match", fetch_next_match)
workflow.add_node("gather_team_stats", gather_team_stats)
workflow.add_node("analyze_data", analyze_data)
workflow.add_node("generate_preview", generate_preview)
workflow.add_node("save_preview_to_db", save_preview_to_db)

workflow.add_edge(START, "fetch_next_match")
workflow.add_conditional_edges("fetch_next_match", check_for_errors)
workflow.add_conditional_edges("gather_team_stats", check_for_errors_stats)
workflow.add_conditional_edges("analyze_data", check_for_errors_analysis)
workflow.add_conditional_edges("generate_preview", check_for_errors_preview)
workflow.add_edge("save_preview_to_db", END)

# Compile
app = workflow.compile()

if __name__ == "__main__":
    print("Starting Multi-Agent LangGraph Workflow...")
    initial_state = AgentState(
        home_team=None, away_team=None, match_time=None,
        home_stats=None, away_stats=None, 
        home_top_players=None, away_top_players=None,
        data_insights=None, preview=None, error=None
    )
    
    result = app.invoke(initial_state)
    
    if result.get("error"):
        print(f"Workflow terminated with error: {result['error']}")
    else:
        print("\n" + "="*50)
        print("DATA ANALYST INSIGHTS")
        print("="*50)
        print(result["data_insights"])
        print("\n" + "="*50)
        print("OFFICIAL MATCH PREVIEW")
        print("="*50)
        print(result["preview"])
        print("="*50)
