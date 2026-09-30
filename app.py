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

# Database initialize
def init_db():
    try:
        with get_db() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT UNIQUE COLLATE NOCASE,
                    answer TEXT
                )
            ''')
            # Base answers
            conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('hello', 'Hello! Kaise madad kar sakta hoon?')")
            conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('kaise ho', 'Main badhiya hoon, aap bataiye!')")
            conn.execute("INSERT OR IGNORE INTO memory (question, answer) VALUES ('who are you', 'Main NanoGPT hoon, ek self-learning AI assistant.')")
            conn.commit()
    except Exception as e:
        print(f"DB Init Error: {e}")

init_db()

def clean_tokens(text):
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
    return set(text.split())

def search_reply(user_query):
    query_tokens = clean_tokens(user_query)
    if not query_tokens:
        return "Kripya koi sawal poochhein."

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            first_few = list(query_tokens)[:3]
            like_clauses = " OR ".join(["question LIKE ?"] * len(first_few))
            params = [f"%{word}%" for word in first_few]
            
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

    except Exception as e:
        print(f"Search error: {e}")

    return "Mujhe ye abhi nahi pata! Mujhe sikhane ke liye type karein: learn: sawal | jawab"

def save_new_fact(question, answer):
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO memory (question, answer) VALUES (?, ?)", (question.strip().lower(), answer.strip()))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception:
        return False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json() or {}
        user_prompt = data.get("prompt", "").strip()

        if not user_prompt:
            return jsonify({"reply": "Kuch type toh kijiye!"})

        if user_prompt.lower().startswith("learn:"):
            try:
                content = user_prompt[6:].strip()
                q_part, a_part = content.split("|")
                if save_new_fact(q_part, a_part):
                    return jsonify({"reply": f"Maine seekh liya: '{q_part.strip()}' -> '{a_part.strip()}'"})
                else:
                    return jsonify({"reply": "Ye sawal pehle se meri memory me hai!"})
            except Exception:
                return jsonify({"reply": "Format galat hai! Aise sikhayein: learn: sawal | jawab"})

        reply = search_reply(user_prompt)
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"System error: {str(e)}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
            
