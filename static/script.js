const chatContainer = document.getElementById("chat-container");
const inputField = document.getElementById("user-input");

// Enter key press support
inputField.addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    handleSend();
  }
});

async function handleSend() {
  const query = inputField.value.trim();
  if (!query) return;

  // 1. User message bubble
  createMessageBubble(query, "user");
  inputField.value = "";

  // 2. AI thinking state bubble
  const aiBubble = createMessageBubble("Thinking...", "ai");

  try {
    // Localhost Python API call
    const response = await fetch("http://127.0.0.1:5000/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ prompt: query })
    });

    const data = await response.json();
    updateAiBubble(aiBubble, data.reply);
  } catch (error) {
    updateAiBubble(aiBubble, "Backend offline! Termux me API running hona zaroori hai.");
  }

  scrollToBottom();
}

function createMessageBubble(text, sender) {
  const msgDiv = document.createElement("div");
  msgDiv.className = `message ${sender}`;

  if (sender === "ai") {
    msgDiv.innerHTML = `
      <div class="sender-tag">NanoGPT</div>
      <div class="bubble-text">${text}</div>
    `;
  } else {
    msgDiv.innerHTML = `<div class="bubble-text">${text}</div>`;
  }

  chatContainer.appendChild(msgDiv);
  scrollToBottom();
  return msgDiv;
}

function updateAiBubble(bubbleElement, newText) {
  const textDiv = bubbleElement.querySelector(".bubble-text");
  if (textDiv) {
    textDiv.innerText = newText;
  }
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}
