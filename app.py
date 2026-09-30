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
    # Naam wale sawal par purana galat memory cache bypass karein
    name_keywords = ["naam", "name", "who are you", "kaun ho", "nanogpt"]
    if any(k in user_query.strip().lower() for k in name_keywords):
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

# 3. Dynamic Active Chat Model Fetcher
def ask_groq_auto(prompt):
    models_url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    available_models = []
    try:
        req = urllib.request.Request(models_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for item in data.get('data', []):
                mid = item.get('id', '')
                # Filter out whisper, guard, vision, and embed models
                if not any(x in mid.lower() for x in ['whisper', 'guard', 'embed', 'distil', 'vision']):
                    available_models.append(mid)
    except Exception as e:
        return None, f"Models fetch failed: {str(e)}"

    if not available_models:
        return None, "Aapke account par koi chat model nahi mila."

    chat_url = "https://api.groq.com/openai/v1/chat/completions"
    last_err = ""
    
    # Strict Language Matching Instructions (SumantX AI)
    system_instruction = (
        "You are SumantX AI, an advanced, fast, and highly intelligent AI assistant created by Sumant. "
        "Your official and only name is SumantX AI. Never introduce yourself as NanoGPT or anything else. "
        "STRICT RULE - LANGUAGE & SCRIPT MIRRORING: "
        "Always detect the exact language, dialect, and script used by the user, and reply strictly in the same language. "
        "1. If the user writes in Hinglish (Hindi written in English alphabet, e.g., 'kaise ho', 'kya kar rahe ho'), "
        "   reply ONLY in Hinglish using the Latin alphabet (A-Z). NEVER use Arabic, Urdu, or Persian script. "
        "2. If the user writes in English, reply in concise English. "
        "3. If the user writes in Hindi (Devanagari, e.g., 'आप कैसे हैं'), reply in Devanagari Hindi. "
        "4. If the user asks in Bhojpuri, Bengali, Marathi, or any regional language, mirror that exact language. "
        "Keep your response strictly to 1-2 direct and clear sentences."
    )

    for selected_model in available_models:
        payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_instruction
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 150
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

    return None, f"Tried models {available_models}. Error: {last_err}"

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

# Endpoint to monitor your growing dataset
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

    # Pehle memory check
    cached = get_cached_reply(user_prompt)
    if cached:
        return jsonify({"reply": cached})

    # AI se direct reply
    reply, err = ask_groq_auto(user_prompt)
    if reply:
        save_to_memory(user_prompt, reply)
        return jsonify({"reply": reply})

    return jsonify({"reply": f"Info: {err}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
