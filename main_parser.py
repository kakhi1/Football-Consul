import time
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")


def setup_database():
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # 1. Match Stats Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_stats (
            match_id TEXT PRIMARY KEY,
            match_date TEXT,
            competition TEXT,
            match_stage TEXT,
            home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            home_formation TEXT, away_formation TEXT,
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
            home_goalkeeper_saves INTEGER, away_goalkeeper_saves INTEGER
        )
    ''')

    # 2. Players Dictionary Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            name TEXT
        )
    ''')

    # 3. Match Lineups (The Bridge Table)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_lineups (
            lineup_id SERIAL PRIMARY KEY,
            match_id TEXT,
            player_id TEXT,
            team_type TEXT, 
            shirt_number TEXT,
            is_starter BOOLEAN,
            rating REAL,
            FOREIGN KEY(match_id) REFERENCES match_stats(match_id),
            FOREIGN KEY(player_id) REFERENCES players(player_id),
            UNIQUE(match_id, player_id)
        )
    ''')

    conn.commit()
    return conn


def get_existing_match_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT match_id FROM match_stats")
    return {row[0] for row in cursor.fetchall()}


def parse_and_save_stats(html_content, conn, match_id, competition, match_stage, home_team, away_team, home_score, away_score):
    """Parses the main Stats tab and saves to match_stats."""
    soup = BeautifulSoup(html_content, 'html.parser')

    stats = {
        'match_id': match_id, 'match_date': None, 'competition': competition, 'match_stage': match_stage,
        'home_team': home_team, 'away_team': away_team,
        'home_score': home_score, 'away_score': away_score,
        'home_formation': None, 'away_formation': None,
        'home_xg': None, 'away_xg': None, 'home_possession': None, 'away_possession': None,
        'home_total_shots': None, 'away_total_shots': None, 'home_shots_on_target': None, 'away_shots_on_target': None,
        'home_shots_off_target': None, 'away_shots_off_target': None, 'home_blocked_shots': None, 'away_blocked_shots': None,
        'home_corners': None, 'away_corners': None, 'home_offsides': None, 'away_offsides': None,
        'home_fouls': None, 'away_fouls': None, 'home_yellow_cards': None, 'away_yellow_cards': None,
        'home_big_chances': None, 'away_big_chances': None, 'home_passes_pct': None, 'away_passes_pct': None,
        'home_goalkeeper_saves': None, 'away_goalkeeper_saves': None
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

    # Extract Statistics
    rows = soup.find_all('div', attrs={'data-testid': 'wcl-statistics'})
    for row in rows:
        category_elem = row.find(
            'div', attrs={'data-testid': 'wcl-statistics-category'})
        if not category_elem:
            continue
        category = category_elem.text.strip()
        values = row.find_all(
            'div', attrs={'data-testid': 'wcl-statistics-value'})

        if len(values) >= 2:
            home_val = values[0].text.split('%')[0].split('(')[0].strip()
            away_val = values[1].text.split('%')[0].split('(')[0].strip()

            try:
                if 'Expected goals' in category:
                    stats['home_xg'], stats['away_xg'] = float(
                        home_val), float(away_val)
                elif 'Ball possession' in category:
                    stats['home_possession'], stats['away_possession'] = int(
                        home_val), int(away_val)
                elif category == 'Total shots':
                    stats['home_total_shots'], stats['away_total_shots'] = int(
                        home_val), int(away_val)
                elif category == 'Shots on target':
                    stats['home_shots_on_target'], stats['away_shots_on_target'] = int(
                        home_val), int(away_val)
                elif category == 'Shots off target':
                    stats['home_shots_off_target'], stats['away_shots_off_target'] = int(
                        home_val), int(away_val)
                elif category == 'Blocked shots':
                    stats['home_blocked_shots'], stats['away_blocked_shots'] = int(
                        home_val), int(away_val)
                elif category == 'Corner kicks':
                    stats['home_corners'], stats['away_corners'] = int(
                        home_val), int(away_val)
                elif category == 'Offsides':
                    stats['home_offsides'], stats['away_offsides'] = int(
                        home_val), int(away_val)
                elif category == 'Fouls':
                    stats['home_fouls'], stats['away_fouls'] = int(
                        home_val), int(away_val)
                elif category == 'Yellow cards':
                    stats['home_yellow_cards'], stats['away_yellow_cards'] = int(
                        home_val), int(away_val)
                elif category == 'Big chances':
                    stats['home_big_chances'], stats['away_big_chances'] = int(
                        home_val), int(away_val)
                elif category == 'Passes':
                    stats['home_passes_pct'], stats['away_passes_pct'] = int(
                        home_val), int(away_val)
                elif category == 'Goalkeeper saves':
                    stats['home_goalkeeper_saves'], stats['away_goalkeeper_saves'] = int(
                        home_val), int(away_val)
            except ValueError:
                continue

    # Insert into Database using Postgres placeholders
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO match_stats 
        VALUES (%(match_id)s, %(match_date)s, %(competition)s, %(match_stage)s, %(home_team)s, %(away_team)s, 
                %(home_score)s, %(away_score)s, %(home_formation)s, %(away_formation)s,
                %(home_xg)s, %(away_xg)s, %(home_possession)s, %(away_possession)s, %(home_total_shots)s, %(away_total_shots)s, 
                %(home_shots_on_target)s, %(away_shots_on_target)s, %(home_shots_off_target)s, %(away_shots_off_target)s, 
                %(home_blocked_shots)s, %(away_blocked_shots)s, %(home_corners)s, %(away_corners)s, %(home_offsides)s, %(away_offsides)s,
                %(home_fouls)s, %(away_fouls)s, %(home_yellow_cards)s, %(away_yellow_cards)s, %(home_big_chances)s, %(away_big_chances)s, 
                %(home_passes_pct)s, %(away_passes_pct)s, %(home_goalkeeper_saves)s, %(away_goalkeeper_saves)s)
        ON CONFLICT (match_id) DO UPDATE SET
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score
    ''', stats)
    conn.commit()


def parse_and_save_lineups(html_content, conn, match_id):
    """Parses the Lineups tab and populates the players and match_lineups tables."""
    soup = BeautifulSoup(html_content, 'html.parser')
    cursor = conn.cursor()

    # 1. Update the Formations in match_stats (Using %s)
    formation_spans = soup.find_all(
        'span', {'data-testid': 'wcl-scores-overline-02'})
    if len(formation_spans) >= 3:
        home_formation = formation_spans[0].text.strip()
        away_formation = formation_spans[2].text.strip()
        cursor.execute('UPDATE match_stats SET home_formation = %s, away_formation = %s WHERE match_id = %s',
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

                    # Postgres requires ON CONFLICT DO NOTHING instead of INSERT OR IGNORE
                    cursor.execute(
                        'INSERT INTO players (player_id, name) VALUES (%s, %s) ON CONFLICT (player_id) DO NOTHING', (player_id, name))

                    cursor.execute('''
                        INSERT INTO match_lineups (match_id, player_id, team_type, shirt_number, is_starter, rating)
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

        print(f"Loading {league_name} results page...")
        page.goto(target_url)
        page.wait_for_selector('.event__match', timeout=10000)

        print(
            f"Expanding all past {league_name} matches... this might take a moment.")
        while True:
            show_more_btn = page.locator("text='Show more matches'")
            if show_more_btn.is_visible():
                try:
                    show_more_btn.click()
                    page.wait_for_timeout(2000)
                except Exception:
                    break
            else:
                break

        main_html = page.content()
        soup = BeautifulSoup(main_html, 'html.parser')
        match_list = []

        current_stage = "Regular Season"

        for element in soup.find_all(['div'], class_=lambda c: c and ('event__round' in c or 'event__match' in c)):
            classes = element.get('class', [])

            if 'event__round' in classes:
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
                            'competition': league_name,
                            'match_stage': current_stage
                        })
                except AttributeError:
                    continue

        print(
            f"\nFound {len(match_list)} finished matches for {league_name}. Beginning deep extraction...\n")

        for m in match_list:
            if m['id'] in existing_ids:
                print(
                    f"⏭️ Skipping {m['home']} vs {m['away']} (Already in DB)")
                continue

            try:
                page.goto(f"https://www.flashscore.com/match/{m['id']}/")
                stats_tab = page.locator(
                    'a[data-analytics-alias="match-statistics"]')
                stats_tab.click(timeout=5000)
                page.wait_for_selector(
                    'div[data-testid="wcl-statistics"]', timeout=5000)
                time.sleep(0.5)

                parse_and_save_stats(page.content(), conn, m['id'], m['competition'], m['match_stage'],
                                     m['home'], m['away'], m['h_score'], m['a_score'])

                lineups_tab = page.locator('a[data-analytics-alias="lineups"]')
                lineups_tab.click(timeout=5000)
                page.wait_for_selector('div.lf__lineUp', timeout=5000)
                time.sleep(0.5)
                parse_and_save_lineups(page.content(), conn, m['id'])

                print(
                    f"✅ Saved Stats & Lineups: {m['home']} {m['h_score']}-{m['a_score']} {m['away']} ({m['match_stage']})")

            except Exception as e:
                print(
                    f"⚠️ Error parsing {m['home']} vs {m['away']}: {e}. Skipping advanced stats.")
                parse_and_save_stats("", conn, m['id'], m['competition'], m['match_stage'],
                                     m['home'], m['away'], m['h_score'], m['a_score'])

            time.sleep(1)

        browser.close()
        conn.close()
        print(f"\n🎉 {league_name} update complete!")


if __name__ == "__main__":
    leagues_to_scrape = [
        {"name": "Premier League",
            "url": "https://www.flashscore.com/football/england/premier-league/results/"},
        {"name": "LaLiga", "url": "https://www.flashscore.com/football/spain/laliga/results/"},
        {"name": "Serie A",
            "url": "https://www.flashscore.com/football/italy/serie-a/results/"},
        {"name": "Bundesliga",
            "url": "https://www.flashscore.com/football/germany/bundesliga/results/"},
        {"name": "Champions League",
            "url": "https://www.flashscore.com/football/europe/champions-league/results/"},
        {"name": "Europa League",
            "url": "https://www.flashscore.com/football/europe/europa-league/results/"},
    ]

    for league in leagues_to_scrape:
        scrape_league(league["name"], league["url"])

    print("\n🏆 All requested leagues have been scraped and saved!")
