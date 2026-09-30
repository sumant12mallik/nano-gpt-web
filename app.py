import os
import re
import sqlite3
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from duckduckgo_search import DDGS

app = Flask(__name__)
CORS(app)

DB_FILE = os.path.join(os.path.dirname(__file__), 'brain.db')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Database Init
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
        conn.commit()

init_db()

def clean_tokens(text):
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
    return set(text.split())

# 1. Database se best match dhundna
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

    if best_reply and best_score >= 0.45:
        return best_reply
    return None

# 2. Web Search Engine (Automatic Internet Lookup)
def search_web_and_summarize(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=2))
            if results and len(results) > 0:
                body = results[0].get('body', '')
                if body:
                    # Precise aur concise answer
                    sentences = re.split(r'(?<=[.!?]) +', body)
                    short_answer = " ".join(sentences[:2]).strip()
                    return short_answer
    except Exception as e:
        print(f"Web Search Error: {e}")
    return None

# 3. Memory me Insert ya Naye Data se Update karna
def save_or_update_memory(question, answer):
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO memory (question, answer) 
                VALUES (?, ?)
                ON CONFLICT(question) DO UPDATE SET 
                    answer = excluded.answer,
                    updated_at = CURRENT_TIMESTAMP
            ''', (question.strip().lower(), answer.strip()))
            conn.commit()
    except Exception as e:
        print(f"DB Update Error: {e}")

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    user_prompt = data.get("prompt", "").strip()

    if not user_prompt:
        return jsonify({"reply": "Kuch sawaal toh puchiye!"})

    # Step 1: Local memory check
    local_reply = search_local_memory(user_prompt)
    if local_reply:
        return jsonify({"reply": local_reply})

    # Step 2: Agar nahi mila toh internet se auto-search
    web_reply = search_web_and_summarize(user_prompt)
    if web_reply:
        # Step 3: Nayi jaankari ko memory me auto-save ya update karna
        save_or_update_memory(user_prompt, web_reply)
        return jsonify({"reply": web_reply})

    return jsonify({"reply": "Mujhe iska uttar internet par nahi mila, kripya thoda alag shabdon me puchein."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
