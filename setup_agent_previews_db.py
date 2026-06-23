import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def setup():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS agent_previews (
            id SERIAL PRIMARY KEY,
            home_team TEXT,
            away_team TEXT,
            match_time TEXT,
            data_insights TEXT,
            preview_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    print("Table agent_previews created successfully.")
    conn.close()

if __name__ == "__main__":
    setup()
