import os
import sqlite3
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

# Groq API Client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY)

DB_FILE = os.path.join(os.path.dirname(__file__), 'brain.db')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Database Initialize
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

# Step 1: Database Memory Check (Superfast response bina API call)
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

# Step 2: Smart & Precise AI Response (Groq Llama-3.1)
def generate_smart_reply(prompt):
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are NanoGPT, an intelligent, fast, and helpful AI assistant created by Sumant. "
                        "Give precise and direct answers in 1-2 short sentences. "
                        "If the user asks in Hindi or Hinglish, reply in clear, friendly conversational Hindi/Hinglish. "
                        "Never give long essays or unnecessary definitions unless asked."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq API Error: {e}")
        return "Abhi network issue hai, kripya thodi der baad dobara puchein."

# Step 3: Self-Learning - Memory me Auto-Save / Update
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

    # Pehle memory check (agar pehle se pata hai to instant bol dega)
    cached = get_cached_reply(user_prompt)
    if cached:
        return jsonify({"reply": cached})

    # Agar naya sawal hai to Groq AI se direct sharp jawab
    smart_reply = generate_smart_reply(user_prompt)
    
    # Aur us nayi jaankari ko memory me auto-save kar lega
    if smart_reply and "issue" not in smart_reply:
        save_to_memory(user_prompt, smart_reply)

    return jsonify({"reply": smart_reply})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
