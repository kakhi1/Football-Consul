import traceback
import requests
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import psycopg2
import os
from dotenv import load_dotenv
import socket

# --- ADD THIS BLOCK TO FORCE IPv4 ---
# This prevents the "Cannot assign requested address" IPv6 error with Neon DB
old_getaddrinfo = socket.getaddrinfo


def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    # Filter out IPv6 (AF_INET6) and only return IPv4 (AF_INET)
    return [response for response in responses if response[0] == socket.AF_INET]


socket.getaddrinfo = new_getaddrinfo
# ------------------------------------
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")


def send_admin_alert(message: str):
    """Sends a direct message to your personal Telegram account."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if token and admin_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        # Add parse_mode="HTML" so Telegram renders the bold and code blocks
        requests.post(url, json={
            "chat_id": admin_id,
            "text": message,
            "parse_mode": "HTML"
        })


def clean_stat_value(val):
    """Extracts the first numeric value from a string (e.g., '48%' -> 48, '1.43' -> 1.43)."""
    if not val:
        return None
    # Check for floats (like xG: 1.43)
    match_float = re.search(r'\d+\.\d+', val)
    if match_float:
        return float(match_float.group())
    # Check for integers (like possession: 48%)
    match_int = re.search(r'\d+', val)
    if match_int:
        return int(match_int.group())
    return None


def setup_database():
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # 1. World Cup Match Stats Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS world_cup_match_stats (
            match_id TEXT PRIMARY KEY,
            match_date TEXT,
            competition TEXT,
            match_stage TEXT,
            home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            home_formation TEXT, away_formation TEXT,
            
            -- Standard Stats
            home_xg REAL, away_xg REAL,
            home_possession_pct INTEGER, away_possession_pct INTEGER,
            home_total_shots INTEGER, away_total_shots INTEGER,
            home_shots_on_target INTEGER, away_shots_on_target INTEGER,
            home_shots_off_target INTEGER, away_shots_off_target INTEGER,
            home_blocked_shots INTEGER, away_blocked_shots INTEGER,
            home_corners INTEGER, away_corners INTEGER,
            home_offsides INTEGER, away_offsides INTEGER,
            home_fouls INTEGER, away_fouls INTEGER,
            home_yellow_cards INTEGER, away_yellow_cards INTEGER,
            home_big_chances INTEGER, away_big_chances INTEGER,
            home_passes_pct INTEGER, away_passes_pct INTEGER,
            home_goalkeeper_saves INTEGER, away_goalkeeper_saves INTEGER,
            
            -- NEW Advanced Stats
            home_xgot REAL, away_xgot REAL,
            home_xa REAL, away_xa REAL,
            home_shots_inside_box INTEGER, away_shots_inside_box INTEGER,
            home_shots_outside_box INTEGER, away_shots_outside_box INTEGER,
            home_hit_woodwork INTEGER, away_hit_woodwork INTEGER,
            home_touches_in_opp_box INTEGER, away_touches_in_opp_box INTEGER,
            home_accurate_through_passes INTEGER, away_accurate_through_passes INTEGER,
            home_free_kicks INTEGER, away_free_kicks INTEGER,
            home_long_passes_pct INTEGER, away_long_passes_pct INTEGER,
            home_passes_final_third_pct INTEGER, away_passes_final_third_pct INTEGER,
            home_crosses_pct INTEGER, away_crosses_pct INTEGER,
            home_throw_ins INTEGER, away_throw_ins INTEGER,
            home_tackles_pct INTEGER, away_tackles_pct INTEGER,
            home_duels_won INTEGER, away_duels_won INTEGER,
            home_clearances INTEGER, away_clearances INTEGER,
            home_interceptions INTEGER, away_interceptions INTEGER,
            home_errors_leading_to_shot INTEGER, away_errors_leading_to_shot INTEGER,
            home_errors_leading_to_goal INTEGER, away_errors_leading_to_goal INTEGER,
            home_xgot_faced REAL, away_xgot_faced REAL,
            home_goals_prevented REAL, away_goals_prevented REAL,
            
            -- Added for World Cup
            home_red_cards INTEGER, away_red_cards INTEGER,
            home_headed_goals INTEGER, away_headed_goals INTEGER
        )
    ''')

    # 2. Players Dictionary Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            name TEXT
        )
    ''')

    # 3. World Cup Match Lineups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS world_cup_match_lineups (
            lineup_id SERIAL PRIMARY KEY,
            match_id TEXT,
            player_id TEXT,
            team_type TEXT, 
            shirt_number TEXT,
            is_starter BOOLEAN,
            rating REAL,
            FOREIGN KEY(match_id) REFERENCES world_cup_match_stats(match_id),
            FOREIGN KEY(player_id) REFERENCES players(player_id),
            UNIQUE(match_id, player_id)
        )
    ''')

    conn.commit()
    return conn


def get_existing_match_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT match_id FROM world_cup_match_stats")
    return {row[0] for row in cursor.fetchall()}


def parse_and_save_stats(html_content, conn, match_id, competition, match_stage, home_team, away_team, home_score, away_score):
    """Parses the main Stats tab and saves to world_cup_match_stats."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. INITIALIZE ALL FIELDS TO NONE
    stats = {
        'match_id': match_id, 'match_date': None, 'competition': competition, 'match_stage': match_stage,
        'home_team': home_team, 'away_team': away_team,
        'home_score': home_score, 'away_score': away_score,
        'home_formation': None, 'away_formation': None,

        # Standard Stats
        'home_xg': None, 'away_xg': None, 'home_possession_pct': None, 'away_possession_pct': None,
        'home_total_shots': None, 'away_total_shots': None, 'home_shots_on_target': None, 'away_shots_on_target': None,
        'home_shots_off_target': None, 'away_shots_off_target': None, 'home_blocked_shots': None, 'away_blocked_shots': None,
        'home_corners': None, 'away_corners': None, 'home_offsides': None, 'away_offsides': None,
        'home_fouls': None, 'away_fouls': None, 'home_yellow_cards': None, 'away_yellow_cards': None,
        'home_big_chances': None, 'away_big_chances': None, 'home_passes_pct': None, 'away_passes_pct': None,
        'home_goalkeeper_saves': None, 'away_goalkeeper_saves': None,

        # Advanced Stats
        'home_xgot': None, 'away_xgot': None, 'home_xa': None, 'away_xa': None,
        'home_shots_inside_box': None, 'away_shots_inside_box': None,
        'home_shots_outside_box': None, 'away_shots_outside_box': None,
        'home_hit_woodwork': None, 'away_hit_woodwork': None,
        'home_touches_in_opp_box': None, 'away_touches_in_opp_box': None,
        'home_accurate_through_passes': None, 'away_accurate_through_passes': None,
        'home_free_kicks': None, 'away_free_kicks': None,
        'home_long_passes_pct': None, 'away_long_passes_pct': None,
        'home_passes_final_third_pct': None, 'away_passes_final_third_pct': None,
        'home_crosses_pct': None, 'away_crosses_pct': None,
        'home_throw_ins': None, 'away_throw_ins': None,
        'home_tackles_pct': None, 'away_tackles_pct': None,
        'home_duels_won': None, 'away_duels_won': None,
        'home_clearances': None, 'away_clearances': None,
        'home_interceptions': None, 'away_interceptions': None,
        'home_errors_leading_to_shot': None, 'away_errors_leading_to_shot': None,
        'home_errors_leading_to_goal': None, 'away_errors_leading_to_goal': None,
        'home_xgot_faced': None, 'away_xgot_faced': None,
        'home_goals_prevented': None, 'away_goals_prevented': None,
        
        # New World Cup Stats
        'home_red_cards': None, 'away_red_cards': None,
        'home_headed_goals': None, 'away_headed_goals': None
    }

    # Extract and format the Match Date
    date_elem = soup.find('div', class_='duelParticipant__startTime')
    if date_elem:
        raw_date = date_elem.text.strip()
        try:
            parsed_date = datetime.strptime(raw_date, "%d.%m.%Y %H:%M")
            stats['match_date'] = parsed_date.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            stats['match_date'] = raw_date

    # Define mapping between Flashscore stat labels and our dictionary keys
    stat_mapping = {
        "Expected goals (xG)": "xg", "xG on target (xGOT)": "xgot", "Expected assists (xA)": "xa",
        "Ball possession": "possession_pct", "Total shots": "total_shots",
        "Shots on target": "shots_on_target", "Shots off target": "shots_off_target",
        "Blocked shots": "blocked_shots", "Shots inside the box": "shots_inside_box",
        "Shots outside the box": "shots_outside_box", "Hit the woodwork": "hit_woodwork",
        "Corner kicks": "corners", "Offsides": "offsides",
        "Touches in opposition box": "touches_in_opp_box", "Accurate through passes": "accurate_through_passes",
        "Free kicks": "free_kicks", "Fouls": "fouls", "Yellow cards": "yellow_cards",
        "Big chances": "big_chances", "Passes": "passes_pct", "Long passes": "long_passes_pct",
        "Passes in final third": "passes_final_third_pct", "Crosses": "crosses_pct",
        "Throw ins": "throw_ins", "Tackles": "tackles_pct", "Duels won": "duels_won",
        "Clearances": "clearances", "Interceptions": "interceptions",
        "Errors leading to shot": "errors_leading_to_shot", "Errors leading to goal": "errors_leading_to_goal",
        "Goalkeeper saves": "goalkeeper_saves", "xGOT faced": "xgot_faced", "Goals prevented": "goals_prevented",
        "Red cards": "red_cards", "Headed goals": "headed_goals"
    }

    # Extract Statistics
    rows = soup.find_all('div', attrs={'data-testid': 'wcl-statistics'})
    for row in rows:
        category_elem = row.find(
            'div', attrs={'data-testid': 'wcl-statistics-category'})
        values = row.find_all(
            'div', attrs={'data-testid': 'wcl-statistics-value'})

        if category_elem and len(values) >= 2:
            category = category_elem.get_text(strip=True)

            for key, suffix in stat_mapping.items():
                if key == category:
                    home_val = values[0].get_text(separator=" ", strip=True)
                    away_val = values[1].get_text(separator=" ", strip=True)

                    stats[f'home_{suffix}'] = clean_stat_value(home_val)
                    stats[f'away_{suffix}'] = clean_stat_value(away_val)
                    break

    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO world_cup_match_stats (
            match_id, match_date, competition, match_stage, home_team, away_team, 
            home_score, away_score, home_formation, away_formation,
            home_xg, away_xg, home_possession_pct, away_possession_pct, home_total_shots, away_total_shots,
            home_shots_on_target, away_shots_on_target, home_shots_off_target, away_shots_off_target,
            home_blocked_shots, away_blocked_shots, home_corners, away_corners, home_offsides, away_offsides,
            home_fouls, away_fouls, home_yellow_cards, away_yellow_cards, home_big_chances, away_big_chances,
            home_passes_pct, away_passes_pct, home_goalkeeper_saves, away_goalkeeper_saves,
            home_xgot, away_xgot, home_xa, away_xa, home_shots_inside_box, away_shots_inside_box,
            home_shots_outside_box, away_shots_outside_box, home_hit_woodwork, away_hit_woodwork,
            home_touches_in_opp_box, away_touches_in_opp_box, home_accurate_through_passes, away_accurate_through_passes,
            home_free_kicks, away_free_kicks, home_long_passes_pct, away_long_passes_pct,
            home_passes_final_third_pct, away_passes_final_third_pct, home_crosses_pct, away_crosses_pct,
            home_throw_ins, away_throw_ins, home_tackles_pct, away_tackles_pct, home_duels_won, away_duels_won,
            home_clearances, away_clearances, home_interceptions, away_interceptions,
            home_errors_leading_to_shot, away_errors_leading_to_shot, home_errors_leading_to_goal, away_errors_leading_to_goal,
            home_xgot_faced, away_xgot_faced, home_goals_prevented, away_goals_prevented,
            home_red_cards, away_red_cards, home_headed_goals, away_headed_goals
        ) VALUES (
            %(match_id)s, %(match_date)s, %(competition)s, %(match_stage)s, %(home_team)s, %(away_team)s, 
            %(home_score)s, %(away_score)s, %(home_formation)s, %(away_formation)s,
            %(home_xg)s, %(away_xg)s, %(home_possession_pct)s, %(away_possession_pct)s, %(home_total_shots)s, %(away_total_shots)s,
            %(home_shots_on_target)s, %(away_shots_on_target)s, %(home_shots_off_target)s, %(away_shots_off_target)s,
            %(home_blocked_shots)s, %(away_blocked_shots)s, %(home_corners)s, %(away_corners)s, %(home_offsides)s, %(away_offsides)s,
            %(home_fouls)s, %(away_fouls)s, %(home_yellow_cards)s, %(away_yellow_cards)s, %(home_big_chances)s, %(away_big_chances)s,
            %(home_passes_pct)s, %(away_passes_pct)s, %(home_goalkeeper_saves)s, %(away_goalkeeper_saves)s,
            %(home_xgot)s, %(away_xgot)s, %(home_xa)s, %(away_xa)s, %(home_shots_inside_box)s, %(away_shots_inside_box)s,
            %(home_shots_outside_box)s, %(away_shots_outside_box)s, %(home_hit_woodwork)s, %(away_hit_woodwork)s,
            %(home_touches_in_opp_box)s, %(away_touches_in_opp_box)s, %(home_accurate_through_passes)s, %(away_accurate_through_passes)s,
            %(home_free_kicks)s, %(away_free_kicks)s, %(home_long_passes_pct)s, %(away_long_passes_pct)s,
            %(home_passes_final_third_pct)s, %(away_passes_final_third_pct)s, %(home_crosses_pct)s, %(away_crosses_pct)s,
            %(home_throw_ins)s, %(away_throw_ins)s, %(home_tackles_pct)s, %(away_tackles_pct)s, %(home_duels_won)s, %(away_duels_won)s,
            %(home_clearances)s, %(away_clearances)s, %(home_interceptions)s, %(away_interceptions)s,
            %(home_errors_leading_to_shot)s, %(away_errors_leading_to_shot)s, %(home_errors_leading_to_goal)s, %(away_errors_leading_to_goal)s,
            %(home_xgot_faced)s, %(away_xgot_faced)s, %(home_goals_prevented)s, %(away_goals_prevented)s,
            %(home_red_cards)s, %(away_red_cards)s, %(home_headed_goals)s, %(away_headed_goals)s
        )
        ON CONFLICT (match_id) DO UPDATE SET
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score
    ''', stats)
    conn.commit()


def parse_and_save_lineups(html_content, conn, match_id):
    """Parses the Lineups tab and populates the players and world_cup_match_lineups tables."""
    soup = BeautifulSoup(html_content, 'html.parser')
    cursor = conn.cursor()

    # 1. ROBUST FORMATION EXTRACTION (Using Regex)
    potential_spans = soup.find_all(
        'span', {'data-testid': 'wcl-scores-overline-02'})
    formations_found = []

    for span in potential_spans:
        text = span.get_text(strip=True)
        # Regex looks for patterns like "4 - 3 - 3" or "4 - 2 - 3 - 1"
        if re.match(r"^\d\s*-\s*\d(?:\s*-\s*\d)*$", text):
            formations_found.append(text)

    # If we successfully found at least 2 formation strings, update the DB
    if len(formations_found) >= 2:
        home_formation = formations_found[0]
        away_formation = formations_found[1]
        cursor.execute('UPDATE world_cup_match_stats SET home_formation = %s, away_formation = %s WHERE match_id = %s',
                       (home_formation, away_formation, match_id))

    # 2. Extract Players
    sections = soup.find_all('div', class_='section')
    for section in sections:
        header = section.find('div', {'data-testid': 'wcl-headerSection-text'})
        if not header:
            continue

        header_text = header.text.lower()
        if 'starting lineups' in header_text:
            is_starter = True
        elif 'substitutes' in header_text:
            is_starter = False
        else:
            continue

        sides = section.find_all('div', class_='lf__side')
        if len(sides) >= 2:
            for side_idx, side_html in enumerate(sides[:2]):
                team_type = 'Home' if side_idx == 0 else 'Away'
                players = side_html.find_all(
                    'div', class_='lf__participantNew')

                for player in players:
                    name_tag = player.find(
                        'span', class_=lambda c: c and 'wcl-name_' in c)
                    if not name_tag:
                        continue

                    name = name_tag.text.strip().replace("(C)", "").replace("(G)", "").strip()
                    player_id = name.lower().replace(" ", "_").replace(".", "")

                    num_tag = player.find(
                        'span', class_=lambda c: c and 'wcl-number_' in c)
                    shirt_number = num_tag.text.strip() if num_tag else None

                    rating_tag = player.find(
                        'span', {'data-testid': 'wcl-scores-caption-05'})
                    rating = float(rating_tag.text.strip()
                                   ) if rating_tag else None

                    cursor.execute(
                        'INSERT INTO players (player_id, name) VALUES (%s, %s) ON CONFLICT (player_id) DO NOTHING',
                        (player_id, name))

                    cursor.execute('''
                        INSERT INTO world_cup_match_lineups (match_id, player_id, team_type, shirt_number, is_starter, rating)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (match_id, player_id) DO NOTHING
                    ''', (match_id, player_id, team_type, shirt_number, is_starter, rating))

    conn.commit()


def scrape_league(league_name, target_url):
    """Generic function to scrape any league passed to it."""
    print(f"\n{'='*50}")
    print(f"🚀 Starting scrape for {league_name}")
    print(f"{'='*50}\n")

    conn = setup_database()
    existing_ids = get_existing_match_ids(conn)
    print(f"Database currently holds {len(existing_ids)} matches.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.route("**/*", lambda route: route.abort()
                   if route.request.resource_type in ["image", "media", "font"]
                   else route.continue_())

        print(f"Loading {league_name} results page...")
        page.goto(target_url, wait_until='domcontentloaded')

        try:
            page.locator('#onetrust-accept-btn-handler').click(timeout=3000)
        except:
            pass

        page.wait_for_selector('.event__match', timeout=10000)

        print(f"Expanding all past {league_name} matches... this might take a moment.")

        clicks = 0
        max_clicks = 5

        while clicks < max_clicks:
            try:
                show_more_btn = page.locator("button:has-text('Show more matches')")

                if show_more_btn.is_visible():
                    show_more_btn.scroll_into_view_if_needed()
                    page.wait_for_timeout(1000)
                    show_more_btn.click(force=True)
                    clicks += 1
                    print(f"Clicked 'Show more matches'... ({clicks}/{max_clicks})")
                    page.wait_for_timeout(3000)
                else:
                    page.keyboard.press("End")
                    page.wait_for_timeout(2000)

                    if show_more_btn.is_visible():
                        continue

                    print("No more matches to load.")
                    break
            except Exception as e:
                print(f"Finished expanding matches. Note: {e}")
                break

        main_html = page.content()
        soup = BeautifulSoup(main_html, 'html.parser')
        match_list = []

        current_stage = "Regular Season"
        current_competition = league_name

        for element in soup.find_all(['div'], class_=lambda c: c and ('event__round' in c or 'event__match' in c or 'wcl-header_' in c or 'headerLeague' in c)):
            classes = element.get('class', [])

            if 'wcl-header_' in classes or 'headerLeague' in classes:
                cat_el = element.find('span', class_=lambda c: c and 'category-text' in c)
                title_el = element.find('span', class_=lambda c: c and 'title-text' in c)
                
                cat = cat_el.text.strip() if cat_el else ""
                title = title_el.text.strip() if title_el else ""
                
                if cat and title:
                    current_competition = f"{cat} - {title}"
                elif title:
                    current_competition = title
                elif cat:
                    current_competition = cat

            elif 'event__round' in classes:
                current_stage = element.text.strip()

            elif 'event__match' in classes:
                match_id_raw = element.get('id')
                if not match_id_raw:
                    continue
                match_id = match_id_raw.split('_')[-1]

                try:
                    home_team = element.find('div', class_='event__homeParticipant').find(
                        'span', class_='wcl-name_jjfMf').text.strip()
                    away_team = element.find('div', class_='event__awayParticipant').find(
                        'span', class_='wcl-name_jjfMf').text.strip()
                    home_score = element.find(
                        'span', class_='event__score--home').text.strip()
                    away_score = element.find(
                        'span', class_='event__score--away').text.strip()

                    if home_score.isdigit() and away_score.isdigit():
                        match_list.append({
                            'id': match_id, 'home': home_team, 'away': away_team,
                            'h_score': int(home_score), 'a_score': int(away_score),
                            'competition': current_competition,
                            'match_stage': current_stage
                        })
                except AttributeError:
                    continue

        print(f"\nFound {len(match_list)} finished matches for {league_name}. Beginning deep extraction...\n")

        for m in match_list:
            if m['id'] in existing_ids:
                print(f"⏭️ Skipping {m['home']} vs {m['away']} (Already in DB)")
                continue

            success = False
            for attempt in range(2):
                try:
                    page.goto(f"https://www.flashscore.com/match/{m['id']}/", wait_until='domcontentloaded')

                    try:
                        page.locator('#onetrust-accept-btn-handler').click(timeout=2000)
                    except:
                        pass

                    # Wait for page to be minimally loaded first
                    page.wait_for_selector('.duelParticipant', timeout=5000)

                    try:
                        stats_tab = page.locator('a[data-analytics-alias="match-statistics"]')
                        if stats_tab.count() > 0 and stats_tab.is_visible():
                            stats_tab.click(timeout=5000, force=True)
                            page.wait_for_selector('div[data-testid="wcl-statistics"]', timeout=5000)

                            parse_and_save_stats(page.content(), conn, m['id'], m['competition'], m['match_stage'],
                                                 m['home'], m['away'], m['h_score'], m['a_score'])
                            stats_success = True
                        else:
                            stats_success = False
                    except Exception as e:
                        conn.rollback()
                        stats_success = False

                    try:
                        lineups_tab = page.locator('a[data-analytics-alias="lineups"]')
                        if lineups_tab.count() > 0 and lineups_tab.is_visible():
                            lineups_tab.click(timeout=5000, force=True)
                            page.wait_for_selector('div.lf__lineUp', timeout=5000)
                            page.wait_for_timeout(1000)

                            parse_and_save_lineups(page.content(), conn, m['id'])
                            lineups_success = True
                        else:
                            lineups_success = False
                    except Exception as e:
                        conn.rollback()
                        lineups_success = False

                    if stats_success or lineups_success:
                        print(f"✅ Saved Stats & Lineups: {m['home']} {m['h_score']}-{m['a_score']} {m['away']} ({m['competition']} - {m['match_stage']})")
                        success = True
                        break
                    else:
                        print(f"⚠️ Missing Stats/Lineups for {m['home']} vs {m['away']}. Skipping deep wait (Attempt {attempt+1}/2)...")
                        time.sleep(1)

                except Exception as e:
                    print(f"⚠️ Network error parsing {m['home']} vs {m['away']}: {e}. Retrying...")
                    time.sleep(2)

            if not success:
                print(f"❌ Completely failed to extract advanced stats for {m['home']} vs {m['away']}. Saving basic info.")
                try:
                    parse_and_save_stats("", conn, m['id'], m['competition'], m['match_stage'],
                                         m['home'], m['away'], m['h_score'], m['a_score'])
                except Exception as e:
                    conn.rollback()
                    print(f"❌ Failed to even save basic info for {m['home']} vs {m['away']}: {e}")

            time.sleep(1)

        browser.close()
        conn.close()
        print(f"\n🎉 {league_name} update complete!")


if __name__ == "__main__":
    try:
        leagues_to_scrape = [
            {"name": "World Championship", "url": "https://www.flashscore.com/football/world/world-championship/results/"}
        ]

        for league in leagues_to_scrape:
            scrape_league(league["name"], league["url"])

        print("\n🏆 All requested leagues have been scraped and saved!")
    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"🚨 <b>PARSER CRASHED!</b>\n\n<b>Error:</b> {e}\n\n<code>{error_details[:500]}</code>"
        send_admin_alert(error_message)
        print("Crash alert sent to admin.")
