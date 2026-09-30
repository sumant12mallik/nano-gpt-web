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

# 3. Live Active Models Fetcher (Kabhi Decommission Error nahi aayega)
def get_active_model():
    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            models = [m['id'] for m in res_data.get('data', []) if 'whisper' not in m['id']]
            # Pehla text-chat model chunein
            if models:
                return models[0]
    except Exception as e:
        print(f"Model list error: {e}")
    # Fallback agar fetch na ho paye
    return "llama-3.1-8b-instant"

# 4. Groq API Call
def ask_groq(prompt):
    active_model = get_active_model()
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    payload = {
        "model": active_model,
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
        return None, f"Model '{active_model}' failed: {err_msg}"
    except Exception as e:
        return None, f"Error: {str(e)}"

# 5. Auto-Save to SQLite Database
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

    # Naya sawal hone par dynamic Groq model call
    reply, err = ask_groq(user_prompt)
    if reply:
        save_to_memory(user_prompt, reply)
        return jsonify({"reply": reply})

    return jsonify({"reply": f"Groq Error: {err}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
