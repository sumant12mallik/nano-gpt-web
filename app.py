import math
import random
import os
from collections import Counter
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 1. Dataset
text_data = [
    "user hello ai hello how can i help you today",
    "user what is your name ai my name is nanogpt assistant",
    "user who are you ai i am an artificial intelligence trained from scratch",
    "user how are you ai i am running perfectly ready to assist you",
    "user what is ai ai ai is future of intelligent systems and learning",
    "user what can you do ai i can process language and generate replies"
]

all_words = []
for sent in text_data:
    all_words.extend(sent.lower().split())

word_counts = Counter(all_words)
vocab = sorted(list(set(all_words)))
vocab_size = len(vocab)
word_to_ix = {w: i for i, w in enumerate(vocab)}
ix_to_word = {i: w for i, w in enumerate(vocab)}

total_tokens = len(all_words)
novelty_bonus = [0.0] * vocab_size
for w, idx in word_to_ix.items():
    freq = word_counts[w] / total_tokens
    novelty_bonus[idx] = -math.log(freq) * 0.1

pairs = []
for sent in text_data:
    words = sent.lower().split()
    for i in range(len(words) - 1):
        pairs.append((word_to_ix[words[i]], word_to_ix[words[i+1]]))

# 2. Weights Matrix aur Training
W = [[random.uniform(-0.1, 0.1) for _ in range(vocab_size)] for _ in range(vocab_size)]

def softmax(logits):
    max_l = max(logits)
    exp_vals = [math.exp(x - max_l) for x in logits]
    s = sum(exp_vals)
    return [x / s for x in exp_vals]

learning_rate = 1.0
epochs = 700

print("--- AI Brain Training in Progress... ---")
for epoch in range(1, epochs + 1):
    for x, target in pairs:
        logits = W[x]
        probs = softmax(logits)
        for j in range(vocab_size):
            grad = probs[j]
            if j == target:
                grad -= 1.0
            W[x][j] -= learning_rate * grad

print("--- AI Brain Ready! ---")

# 3. Response Engine
def generate_reply(user_text, max_new_words=10, rep_penalty=1.4, top_k=2):
    full_prompt = f"user {user_text.lower()} ai"
    words = full_prompt.split()
    generated = list(words)
    
    for _ in range(max_new_words):
        last_word = generated[-1]
        if last_word not in word_to_ix:
            last_word = random.choice(vocab)
            
        x = word_to_ix[last_word]
        logits = list(W[x])
        
        for j in range(vocab_size):
            logits[j] += 0.2 * novelty_bonus[j]
        for w in set(generated[-3:]):
            if w in word_to_ix:
                logits[word_to_ix[w]] /= rep_penalty
                
        probs = softmax(logits)
        indexed = sorted(list(enumerate(probs)), key=lambda item: item[1], reverse=True)[:top_k]
        top_indices = [item[0] for item in indexed]
        top_probs = softmax([item[1] for item in indexed])
        
        chosen_id = random.choices(top_indices, weights=top_probs)[0]
        next_word = ix_to_word[chosen_id]
        
        if next_word == "user":
            break
        generated.append(next_word)
        
    return " ".join(generated[len(words):])

# 4. Frontend Route (Homepage UI)
@app.route('/')
def home():
    return render_template('index.html')

# 5. API Route (Chat Backend)
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_prompt = data.get("prompt", "")
    if not user_prompt:
        return jsonify({"reply": "Please enter a valid message."})
    
    bot_reply = generate_reply(user_prompt)
    if not bot_reply.strip():
        bot_reply = "I understand, tell me more."
        
    return jsonify({"reply": bot_reply})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
