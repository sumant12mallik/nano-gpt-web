import os
import re
import json
import sqlite3
import urllib.request
import urllib.parse
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_FILE = os.path.join(os.path.dirname(__file__), 'brain.db')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT UNIQUE COLLATE NOCASE,
                answer TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Default conversational replies
        conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('hii', 'Hello! Kaise madad kar sakta hoon?')")
        conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('kaise ho', 'Main badhiya hoon, aap bataiye!')")
        conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('who are you', 'Main NanoGPT hoon, ek self-learning AI assistant.')")
        conn.commit()

init_db()

def clean_tokens(text):
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
    return set(text.split())

# 1. Local Memory Search
def search_local_memory(user_query):
    query_tokens = clean_tokens(user_query)
    if not query_tokens:
        return None

    first_few = list(query_tokens)[:3]
    like_clauses = " OR ".join(["question LIKE ?"] * len(first_few))
    params = [f"%{word}%" for word in first_few]

    with get_db() as conn:
        cursor = conn.cursor()
        if like_clauses:
            cursor.execute(f"SELECT question, answer FROM memory WHERE {like_clauses} LIMIT 30", params)
        else:
            cursor.execute("SELECT question, answer FROM memory LIMIT 30")
        rows = cursor.fetchall()

    best_score = 0.0
    best_reply = None

    for row in rows:
        q_tokens = clean_tokens(row['question'])
        if not q_tokens:
            continue
        score = len(query_tokens.intersection(q_tokens)) / len(query_tokens.union(q_tokens))
        if score > best_score:
            best_score = score
            best_reply = row['answer']

    if best_reply and best_score >= 0.40:
        return best_reply
    return None

# 2. Free & Unblocked Web Search (Wikipedia + Instant API)
def search_web(query):
    # Stop words hatakar main topic nikalna (jaise 'india president')
    stop_words = {"ka", "ki", "ke", "hai", "kon", "kaun", "kya", "batao", "who", "is", "the", "of", "what"}
    words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', query.lower()).split() if w not in stop_words]
    search_term = " ".join(words) if words else query

    headers = {'User-Agent': 'NanoGPT-AI/1.0 (Educational Project)'}

    # Step A: Direct Wikipedia Summary API (Never blocked on Render)
    try:
        encoded = urllib.parse.quote(search_term)
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(wiki_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            extract = data.get("extract")
            if extract:
                sentences = re.split(r'(?<=[.!?]) +', extract)
                return " ".join(sentences[:2]).strip()
    except Exception:
        pass

    # Step B: Wikipedia Search Query (Agar exact title na mile)
    try:
        search_api = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(search_term)}&utf8=&format=json"
        req = urllib.request.Request(search_api, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            results = data.get("query", {}).get("search", [])
            if results:
                snippet = results[0].get("snippet", "")
                # HTML tags hatana
                clean_snippet = re.sub(r'<[^>]+>', '', snippet)
                if clean_snippet:
                    return f"{results[0].get('title')}: {clean_snippet}..."
    except Exception as e:
        print(f"Search API error: {e}")

    return None

# 3. Memory Update
def save_to_memory(question, answer):
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO memory (question, answer) VALUES (?, ?)
                ON CONFLICT(question) DO UPDATE SET 
                    answer = excluded.answer,
                    updated_at = CURRENT_TIMESTAMP
            ''', (question.strip().lower(), answer.strip()))
            conn.commit()
    except Exception as e:
        print(f"Memory Save Error: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    user_prompt = data.get("prompt", "").strip()

    if not user_prompt:
        return jsonify({"reply": "Kuch toh puchiye!"})

    # 1. Local Memory Check
    local_reply = search_local_memory(user_prompt)
    if local_reply:
        return jsonify({"reply": local_reply})

    # 2. Internet Search
    web_reply = search_web(user_prompt)
    if web_reply:
        save_to_memory(user_prompt, web_reply)
        return jsonify({"reply": web_reply})

    return jsonify({"reply": "Mujhe iska jawab nahi mila, kripya thoda alag shabdon me puchein."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
