# import sqlite3
# import time
# from bs4 import BeautifulSoup
# from playwright.sync_api import sync_playwright


# def setup_database():
#     conn = sqlite3.connect('football_consul.db')
#     cursor = conn.cursor()
#     # Expanded Schema to hold all the new data!
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS match_stats (
#             match_id TEXT PRIMARY KEY,
#             home_team TEXT,
#             away_team TEXT,
#             home_score INTEGER,
#             away_score INTEGER,

#             home_xg REAL, away_xg REAL,
#             home_possession_pct INTEGER, away_possession_pct INTEGER,
#             home_total_shots INTEGER, away_total_shots INTEGER,
#             home_shots_on_target INTEGER, away_shots_on_target INTEGER,
#             home_shots_off_target INTEGER, away_shots_off_target INTEGER,
#             home_blocked_shots INTEGER, away_blocked_shots INTEGER,
#             home_corners INTEGER, away_corners INTEGER,
#             home_offsides INTEGER, away_offsides INTEGER,
#             home_fouls INTEGER, away_fouls INTEGER,
#             home_yellow_cards INTEGER, away_yellow_cards INTEGER,
#             home_big_chances INTEGER, away_big_chances INTEGER,
#             home_passes_pct INTEGER, away_passes_pct INTEGER,
#             home_goalkeeper_saves INTEGER, away_goalkeeper_saves INTEGER
#         )
#     ''')
#     conn.commit()
#     return conn


# def get_existing_match_ids(conn):
#     cursor = conn.cursor()
#     cursor.execute("SELECT match_id FROM match_stats")
#     return {row[0] for row in cursor.fetchall()}


# def parse_and_save_stats(html_content, conn, match_id, home_team, away_team, home_score, away_score):
#     soup = BeautifulSoup(html_content, 'html.parser')

#     # Initialize everything as None (NULL)
#     stats = {
#         'match_id': match_id, 'home_team': home_team, 'away_team': away_team,
#         'home_score': home_score, 'away_score': away_score,
#         'home_xg': None, 'away_xg': None,
#         'home_possession': None, 'away_possession': None,
#         'home_total_shots': None, 'away_total_shots': None,
#         'home_shots_on_target': None, 'away_shots_on_target': None,
#         'home_shots_off_target': None, 'away_shots_off_target': None,
#         'home_blocked_shots': None, 'away_blocked_shots': None,
#         'home_corners': None, 'away_corners': None,
#         'home_offsides': None, 'away_offsides': None,
#         'home_fouls': None, 'away_fouls': None,
#         'home_yellow_cards': None, 'away_yellow_cards': None,
#         'home_big_chances': None, 'away_big_chances': None,
#         'home_passes_pct': None, 'away_passes_pct': None,
#         'home_goalkeeper_saves': None, 'away_goalkeeper_saves': None
#     }

#     rows = soup.find_all('div', attrs={'data-testid': 'wcl-statistics'})

#     for row in rows:
#         category_elem = row.find(
#             'div', attrs={'data-testid': 'wcl-statistics-category'})
#         if not category_elem:
#             continue
#         category = category_elem.text.strip()

#         values = row.find_all(
#             'div', attrs={'data-testid': 'wcl-statistics-value'})

#         if len(values) >= 2:
#             home_val_raw = values[0].text.strip()
#             away_val_raw = values[1].text.strip()

#             # This cleanly extracts numbers even if it says "78% (256/328)" -> "78"
#             home_val = home_val_raw.split('%')[0].split('(')[0].strip()
#             away_val = away_val_raw.split('%')[0].split('(')[0].strip()

#             try:
#                 if 'Expected goals' in category:
#                     stats['home_xg'] = float(home_val)
#                     stats['away_xg'] = float(away_val)
#                 elif 'Ball possession' in category:
#                     stats['home_possession'] = int(home_val)
#                     stats['away_possession'] = int(away_val)
#                 elif category == 'Total shots':
#                     stats['home_total_shots'] = int(home_val)
#                     stats['away_total_shots'] = int(away_val)
#                 elif category == 'Shots on target':
#                     stats['home_shots_on_target'] = int(home_val)
#                     stats['away_shots_on_target'] = int(away_val)
#                 elif category == 'Shots off target':
#                     stats['home_shots_off_target'] = int(home_val)
#                     stats['away_shots_off_target'] = int(away_val)
#                 elif category == 'Blocked shots':
#                     stats['home_blocked_shots'] = int(home_val)
#                     stats['away_blocked_shots'] = int(away_val)
#                 elif category == 'Corner kicks':
#                     stats['home_corners'] = int(home_val)
#                     stats['away_corners'] = int(away_val)
#                 elif category == 'Offsides':
#                     stats['home_offsides'] = int(home_val)
#                     stats['away_offsides'] = int(away_val)
#                 elif category == 'Fouls':
#                     stats['home_fouls'] = int(home_val)
#                     stats['away_fouls'] = int(away_val)
#                 elif category == 'Yellow cards':
#                     stats['home_yellow_cards'] = int(home_val)
#                     stats['away_yellow_cards'] = int(away_val)
#                 elif category == 'Big chances':
#                     stats['home_big_chances'] = int(home_val)
#                     stats['away_big_chances'] = int(away_val)
#                 elif category == 'Passes':
#                     stats['home_passes_pct'] = int(home_val)
#                     stats['away_passes_pct'] = int(away_val)
#                 elif category == 'Goalkeeper saves':
#                     stats['home_goalkeeper_saves'] = int(home_val)
#                     stats['away_goalkeeper_saves'] = int(away_val)
#             except ValueError:
#                 continue

#     cursor = conn.cursor()

#     # We use a dictionary unpacking trick (**stats) to make the SQL cleaner
#     cursor.execute('''
#         INSERT OR REPLACE INTO match_stats
#         VALUES (:match_id, :home_team, :away_team, :home_score, :away_score,
#                 :home_xg, :away_xg, :home_possession, :away_possession,
#                 :home_total_shots, :away_total_shots, :home_shots_on_target, :away_shots_on_target,
#                 :home_shots_off_target, :away_shots_off_target, :home_blocked_shots, :away_blocked_shots,
#                 :home_corners, :away_corners, :home_offsides, :away_offsides,
#                 :home_fouls, :away_fouls, :home_yellow_cards, :away_yellow_cards,
#                 :home_big_chances, :away_big_chances, :home_passes_pct, :away_passes_pct,
#                 :home_goalkeeper_saves, :away_goalkeeper_saves)
#     ''', stats)
#     conn.commit()
#     print(f"✅ Saved match: {home_team} {home_score}-{away_score} {away_team}")


# def scrape_premier_league():
#     conn = setup_database()
#     existing_ids = get_existing_match_ids(conn)
#     print(f"Database currently holds {len(existing_ids)} matches.")

#     target_url = "https://www.flashscore.com/football/england/premier-league/results/"

#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=True)
#         page = browser.new_page()

#         print("Loading Premier League results page...")
#         page.goto(target_url)
#         page.wait_for_selector('.event__match', timeout=10000)

#         print("Expanding all past matches... this might take a moment.")
#         while True:
#             show_more_btn = page.locator("text='Show more matches'")
#             if show_more_btn.is_visible():
#                 try:
#                     show_more_btn.click()
#                     page.wait_for_timeout(2000)
#                 except Exception:
#                     break
#             else:
#                 break

#         main_html = page.content()
#         soup = BeautifulSoup(main_html, 'html.parser')
#         match_elements = soup.find_all('div', class_='event__match')
#         match_list = []

#         for match in match_elements:
#             match_id_raw = match.get('id')
#             if not match_id_raw:
#                 continue
#             match_id = match_id_raw.split('_')[-1]

#             try:
#                 home_team = match.find('div', class_='event__homeParticipant').find(
#                     'span', class_='wcl-name_jjfMf').text.strip()
#                 away_team = match.find('div', class_='event__awayParticipant').find(
#                     'span', class_='wcl-name_jjfMf').text.strip()
#                 home_score = match.find(
#                     'span', class_='event__score--home').text.strip()
#                 away_score = match.find(
#                     'span', class_='event__score--away').text.strip()

#                 if home_score.isdigit() and away_score.isdigit():
#                     match_list.append({
#                         'id': match_id, 'home': home_team, 'away': away_team,
#                         'h_score': int(home_score), 'a_score': int(away_score)
#                     })
#             except AttributeError:
#                 continue

#         print(
#             f"\nFound {len(match_list)} finished matches. Beginning stats extraction...\n")

#         for m in match_list:
#             if m['id'] in existing_ids:
#                 print(
#                     f"⏭️ Skipping {m['home']} vs {m['away']} (Already in DB)")
#                 continue

#             try:
#                 page.goto(f"https://www.flashscore.com/match/{m['id']}/")

#                 stats_tab = page.locator(
#                     'a[data-analytics-alias="match-statistics"]')
#                 stats_tab.click(timeout=5000)

#                 page.wait_for_selector(
#                     'div[data-testid="wcl-statistics"]', timeout=5000)
#                 time.sleep(0.5)

#                 stats_html = page.content()
#                 parse_and_save_stats(
#                     stats_html, conn, m['id'], m['home'], m['away'], m['h_score'], m['a_score'])

#             except Exception:
#                 print(
#                     f"⚠️ No detailed stats found for {m['home']} vs {m['away']}. Saving basic score only.")
#                 parse_and_save_stats(
#                     "", conn, m['id'], m['home'], m['away'], m['h_score'], m['a_score'])

#             time.sleep(1)

#         browser.close()
#         conn.close()
#         print("\n🎉 Update complete!")


# if __name__ == "__main__":
#     scrape_premier_league()


import sqlite3
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DB_PATH = 'football_consul.db'


def setup_database():
    """Initializes the normalized database schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Match Stats Table (Now with formation columns)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_stats (
            match_id TEXT PRIMARY KEY,
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
            lineup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            player_id TEXT,
            team_type TEXT, 
            shirt_number TEXT,
            is_starter BOOLEAN,
            rating REAL,
            FOREIGN KEY(match_id) REFERENCES match_stats(match_id),
            FOREIGN KEY(player_id) REFERENCES players(player_id)
        )
    ''')

    conn.commit()
    return conn


def get_existing_match_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT match_id FROM match_stats")
    return {row[0] for row in cursor.fetchall()}


def parse_and_save_stats(html_content, conn, match_id, home_team, away_team, home_score, away_score):
    """Parses the main Stats tab and saves to match_stats."""
    soup = BeautifulSoup(html_content, 'html.parser')

    stats = {
        'match_id': match_id, 'home_team': home_team, 'away_team': away_team,
        'home_score': home_score, 'away_score': away_score,
        # Will be updated by lineups parser
        'home_formation': None, 'away_formation': None,
        'home_xg': None, 'away_xg': None, 'home_possession': None, 'away_possession': None,
        'home_total_shots': None, 'away_total_shots': None, 'home_shots_on_target': None, 'away_shots_on_target': None,
        'home_shots_off_target': None, 'away_shots_off_target': None, 'home_blocked_shots': None, 'away_blocked_shots': None,
        'home_corners': None, 'away_corners': None, 'home_offsides': None, 'away_offsides': None,
        'home_fouls': None, 'away_fouls': None, 'home_yellow_cards': None, 'away_yellow_cards': None,
        'home_big_chances': None, 'away_big_chances': None, 'home_passes_pct': None, 'away_passes_pct': None,
        'home_goalkeeper_saves': None, 'away_goalkeeper_saves': None
    }

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

    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO match_stats 
        VALUES (:match_id, :home_team, :away_team, :home_score, :away_score, :home_formation, :away_formation,
                :home_xg, :away_xg, :home_possession, :away_possession, :home_total_shots, :away_total_shots, 
                :home_shots_on_target, :away_shots_on_target, :home_shots_off_target, :away_shots_off_target, 
                :home_blocked_shots, :away_blocked_shots, :home_corners, :away_corners, :home_offsides, :away_offsides,
                :home_fouls, :away_fouls, :home_yellow_cards, :away_yellow_cards, :home_big_chances, :away_big_chances, 
                :home_passes_pct, :away_passes_pct, :home_goalkeeper_saves, :away_goalkeeper_saves)
    ''', stats)
    conn.commit()


def parse_and_save_lineups(html_content, conn, match_id):
    """Parses the Lineups tab and populates the players and match_lineups tables."""
    soup = BeautifulSoup(html_content, 'html.parser')
    cursor = conn.cursor()

    # 1. Update the Formations in match_stats
    formation_spans = soup.find_all(
        'span', {'data-testid': 'wcl-scores-overline-02'})
    if len(formation_spans) >= 3:
        home_formation = formation_spans[0].text.strip()
        away_formation = formation_spans[2].text.strip()
        cursor.execute('UPDATE match_stats SET home_formation = ?, away_formation = ? WHERE match_id = ?',
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
                    # FIX: Specifically target the span with the name class, not just the testid
                    name_tag = player.find(
                        'span', class_=lambda c: c and 'wcl-name_' in c)
                    if not name_tag:
                        continue

                    name = name_tag.text.strip()

                    # Clean up captain (C) or goalkeeper (G) tags if they accidentally bleed in
                    name = name.replace("(C)", "").replace("(G)", "").strip()

                    # Create a clean ID for the database
                    player_id = name.lower().replace(" ", "_").replace(".", "")

                    # FIX: Specifically target the span with the number class
                    num_tag = player.find(
                        'span', class_=lambda c: c and 'wcl-number_' in c)
                    shirt_number = num_tag.text.strip() if num_tag else None

                    rating_tag = player.find(
                        'span', {'data-testid': 'wcl-scores-caption-05'})
                    rating = float(rating_tag.text.strip()
                                   ) if rating_tag else None

                    # Insert player dictionary (ignores if they already exist)
                    cursor.execute(
                        'INSERT OR IGNORE INTO players (player_id, name) VALUES (?, ?)', (player_id, name))

                    # Insert match connection
                    cursor.execute('''
                        INSERT INTO match_lineups (match_id, player_id, team_type, shirt_number, is_starter, rating)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (match_id, player_id, team_type, shirt_number, is_starter, rating))

    conn.commit()


def scrape_premier_league():
    conn = setup_database()
    existing_ids = get_existing_match_ids(conn)
    print(f"Database currently holds {len(existing_ids)} matches.")

    target_url = "https://www.flashscore.com/football/england/premier-league/results/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Loading Premier League results page...")
        page.goto(target_url)
        page.wait_for_selector('.event__match', timeout=10000)

        print("Expanding all past matches... this might take a moment.")
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
        match_elements = soup.find_all('div', class_='event__match')
        match_list = []

        for match in match_elements:
            match_id_raw = match.get('id')
            if not match_id_raw:
                continue
            match_id = match_id_raw.split('_')[-1]

            try:
                home_team = match.find('div', class_='event__homeParticipant').find(
                    'span', class_='wcl-name_jjfMf').text.strip()
                away_team = match.find('div', class_='event__awayParticipant').find(
                    'span', class_='wcl-name_jjfMf').text.strip()
                home_score = match.find(
                    'span', class_='event__score--home').text.strip()
                away_score = match.find(
                    'span', class_='event__score--away').text.strip()

                if home_score.isdigit() and away_score.isdigit():
                    match_list.append({
                        'id': match_id, 'home': home_team, 'away': away_team,
                        'h_score': int(home_score), 'a_score': int(away_score)
                    })
            except AttributeError:
                continue

        print(
            f"\nFound {len(match_list)} finished matches. Beginning deep extraction...\n")

        for m in match_list:
            if m['id'] in existing_ids:
                print(
                    f"⏭️ Skipping {m['home']} vs {m['away']} (Already in DB)")
                continue

            try:
                # 1. Extract Stats
                page.goto(f"https://www.flashscore.com/match/{m['id']}/")
                stats_tab = page.locator(
                    'a[data-analytics-alias="match-statistics"]')
                stats_tab.click(timeout=5000)
                page.wait_for_selector(
                    'div[data-testid="wcl-statistics"]', timeout=5000)
                time.sleep(0.5)
                parse_and_save_stats(
                    page.content(), conn, m['id'], m['home'], m['away'], m['h_score'], m['a_score'])

                # 2. Extract Lineups (NEW)
                lineups_tab = page.locator('a[data-analytics-alias="lineups"]')
                lineups_tab.click(timeout=5000)
                page.wait_for_selector('div.lf__lineUp', timeout=5000)
                time.sleep(0.5)
                parse_and_save_lineups(page.content(), conn, m['id'])

                print(
                    f"✅ Saved Stats & Lineups: {m['home']} {m['h_score']}-{m['a_score']} {m['away']}")

            except Exception as e:
                print(
                    f"⚠️ Error parsing {m['home']} vs {m['away']}: {e}. Skipping advanced stats.")
                # We still save the base match if advanced stats fail
                parse_and_save_stats(
                    "", conn, m['id'], m['home'], m['away'], m['h_score'], m['a_score'])

            time.sleep(1)

        browser.close()
        conn.close()
        print("\n🎉 Update complete!")


if __name__ == "__main__":
    scrape_premier_league()
