from flask import Flask, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS so the web frontend can call the API

DB_URL = os.getenv("DATABASE_URL")

@app.route('/api/previews', methods=['GET'])
def get_previews():
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Fetch the latest 10 previews
        query = """
            SELECT id, home_team, away_team, match_time, data_insights, preview_text, created_at 
            FROM agent_previews
            ORDER BY created_at DESC
            LIMIT 10
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        conn.close()
        
        # Convert datetime objects to string for JSON serialization
        for row in rows:
            if 'created_at' in row and row['created_at']:
                row['created_at'] = row['created_at'].isoformat()
                
        return jsonify({"status": "success", "data": rows}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("Starting Football Consul API on port 5000...")
    app.run(debug=True, port=5000)
