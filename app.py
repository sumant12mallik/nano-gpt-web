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
    # Name aur greetings ko cache se bypass karein taaki galat purana text na uthaye
    bypass_words = ["naam", "name", "who are you", "kaun ho", "hii", "hi", "hello", "hey"]
    if any(k in user_query.strip().lower() for k in bypass_words):
        return None

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

# 3. Chat Completion Function
def ask_groq_auto(prompt):
    chat_url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    # Best production chat models in order
    preferred_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768"
    ]

    # Concrete and Strict System Prompt
    system_instruction = (
        "You are SumantX AI, an intelligent, conversational AI assistant created by Sumant. "
        "Your name is strictly SumantX AI. Never say you are NanoGPT, Llama, or any other model. "
        "LANGUAGE MATCHING RULE: "
        "Strictly identify the language and script of the user's input and reply in that EXACT SAME language and script. "
        "- If user speaks Hinglish (Hindi words written in English letters like 'kaise ho', 'kya kar rahe ho'), reply ONLY in Hinglish using English letters. Never use Arabic, Urdu, or Devanagari script. "
        "- If user speaks English, reply in English. "
        "- If user speaks Hindi (Devanagari script like 'नमस्ते'), reply in Hindi Devanagari script. "
        "- If user speaks Bengali, Bhojpuri, Punjabi, Gujarati, etc., reply in that specific language. "
        "Do not provide translations. Keep your answers direct, friendly, and natural."
    )

    last_err = ""
    for selected_model in preferred_models:
        payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_instruction
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 200
        }

        try:
            chat_req = urllib.request.Request(chat_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(chat_req, timeout=12) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data['choices'][0]['message']['content'].strip(), None
        except urllib.error.HTTPError as e:
            last_err = f"{selected_model}: {e.read().decode('utf-8')}"
            continue
        except Exception as e:
            last_err = str(e)
            continue

    return None, f"Error: {last_err}"

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

@app.route('/dataset')
def show_dataset():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, question, answer, updated_at FROM memory ORDER BY id DESC")
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
    return jsonify({
        "total_learned": len(data),
        "data": data
    })

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    user_prompt = data.get("prompt", "").strip()

    if not user_prompt:
        return jsonify({"reply": "Kuch sawaal poochhein."})

    # Memory Cache check
    cached = get_cached_reply(user_prompt)
    if cached:
        return jsonify({"reply": cached})

    # AI Model call
    reply, err = ask_groq_auto(user_prompt)
    if reply:
        save_to_memory(user_prompt, reply)
        return jsonify({"reply": reply})

    return jsonify({"reply": f"Info: {err}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
