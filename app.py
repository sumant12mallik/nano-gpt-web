import os
import json
import sqlite3
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
DB_FILE = os.path.join(os.path.dirname(__file__), 'brain.db')

# Groq ke active models ki list (ek fail hua toh turant agla chalega)
ACTIVE_MODELS = [
    "llama-3.2-3b-preview",
    "llama-3.2-1b-preview",
    "mixtral-8x7b-32768",
    "gemma2-9b-it"
]

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# 1. Database Initialize
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

# 2. Local Memory Check
def get_cached_reply(user_query):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT answer FROM memory WHERE question = ? LIMIT 1", (user_query.strip().lower(),))
            row = cursor.fetchone()
            if row:
                return row['answer']
    except Exception:
        pass
    return None

# 3. Groq API Call with Multi-Model Fallback
def ask_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    last_error = None

    for model_name in ACTIVE_MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are NanoGPT, a sharp, precise, and helpful AI assistant created by Sumant. "
                        "Provide accurate, direct answers in 1-2 sentences. "
                        "If asked in Hindi or Hinglish, reply in natural, fluent Hindi/Hinglish."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 150
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=12) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data['choices'][0]['message']['content'].strip(), None
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            last_error = f"{model_name} failed: {err_msg}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    return None, last_error

# 4. Auto-Save to SQLite Database
def save_to_memory(question, answer):
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO memory (question, answer) VALUES (?, ?)
                ON CONFLICT(question) DO UPDATE SET 
                    answer = excluded.answer,
                    updated_at = CURRENT_TIMESTAMP
            ''', (question.strip().lower(), answer))
            conn.commit()
    except Exception as e:
        print(f"DB Save Error: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    user_prompt = data.get("prompt", "").strip()

    if not user_prompt:
        return jsonify({"reply": "Kripya koi sawal poochhein."})

    # Pehle memory check
    cached = get_cached_reply(user_prompt)
    if cached:
        return jsonify({"reply": cached})

    # Naya sawal hone par LLM call
    reply, err = ask_groq(user_prompt)
    if reply:
        save_to_memory(user_prompt, reply)
        return jsonify({"reply": reply})

    return jsonify({"reply": f"Groq Error: {err}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
