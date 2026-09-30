import os
import re
import sqlite3
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_FILE = os.path.join(os.path.dirname(__file__), 'brain.db')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# 1. Database Setup (Zero RAM Usage)
def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT UNIQUE COLLATE NOCASE,
                answer TEXT
            )
        ''')
        # Base knowledge default entries
        conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('hello', 'Hello! How can I assist you today?')")
        conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('who are you', 'I am NanoGPT, built by Sumant.')")
        conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('what is ai', 'AI is the simulation of human intelligence by computers.')")
        conn.commit()

init_db()

def clean_tokens(text):
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
    return set(text.split())

# 2. Disk-Based Search & Self-Learning
def search_reply(user_query):
    query_tokens = clean_tokens(user_query)
    if not query_tokens:
        return "Please ask a valid question."

    # SQLite se keywords ke base par lightweight filtering
    first_few = list(query_tokens)[:3]
    like_clauses = " OR ".join(["question LIKE ?"] * len(first_few))
    params = [f"%{word}%" for word in first_few]
    
    with get_db() as conn:
        cursor = conn.cursor()
        if like_clauses:
            cursor.execute(f"SELECT question, answer FROM memory WHERE {like_clauses} LIMIT 50", params)
        else:
            cursor.execute("SELECT question, answer FROM memory LIMIT 50")
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

    if best_reply and best_score >= 0.25:
        return best_reply

    return "I don't know this yet! Teach me: learn: [Question] | [Answer]"

def save_new_fact(question, answer):
    q_clean = question.strip().lower()
    a_clean = answer.strip()
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO memory (question, answer) VALUES (?, ?)", (q_clean, a_clean))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        # SQLite duplicate question ko automatically block kar dega
        return False

# 3. Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    user_prompt = data.get("prompt", "").strip()

    if not user_prompt:
        return jsonify({"reply": "Please enter a message."})

    # Self-learning command
    if user_prompt.lower().startswith("learn:"):
        try:
            content = user_prompt[6:].strip()
            q_part, a_part = content.split("|")
            success = save_new_fact(q_part, a_part)
            if success:
                return jsonify({"reply": f"Learned successfully: '{q_part.strip()}' -> '{a_part.strip()}'"})
            else:
                return jsonify({"reply": "I already have this exact concept in my database!"})
        except Exception:
            return jsonify({"reply": "Format: learn: Question | Answer"})

    return jsonify({"reply": search_reply(user_prompt)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
