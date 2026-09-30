const chatContainer = document.getElementById("chat-container");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

function addMessage(sender, text, isAi = false) {
  const msgDiv = document.createElement("div");
  msgDiv.className = `message ${isAi ? "ai" : "user"}`;

  if (isAi) {
    const senderTag = document.createElement("div");
    senderTag.className = "sender-tag";
    senderTag.innerText = "NanoGPT";
    msgDiv.appendChild(senderTag);
  }

  const textNode = document.createElement("div");
  textNode.innerText = text;
  msgDiv.appendChild(textNode);

  chatContainer.appendChild(msgDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  return msgDiv;
}

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  // User ka message dikhayein
  addMessage("You", text, false);
  userInput.value = "";

  // Thinking bubble banayein
  const thinkingMsg = addMessage("NanoGPT", "Thinking...", true);

  try {
    // Relative path '/chat' use hoga Render ke liye
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ prompt: text })
    });

    if (!response.ok) {
      throw new Error(`Server status: ${response.status}`);
    }

    const data = await response.json();
    thinkingMsg.querySelector("div:last-child").innerText = data.reply || "No reply received.";

  } catch (error) {
    console.error("Chat error:", error);
    thinkingMsg.querySelector("div:last-child").innerText = "Network ya server error aaya! Thodi der baad try karein.";
  }
}

// Button click aur Enter key listener
if (sendBtn) {
  sendBtn.addEventListener("click", sendMessage);
}

if (userInput) {
  userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      sendMessage();
    }
  });
}
