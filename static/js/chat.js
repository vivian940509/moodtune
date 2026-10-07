const chatForm = document.querySelector("#chatCompose");
const chatMessages = document.querySelector("#chatMessages");

if (chatForm && chatMessages) {
  chatMessages.scrollTop = chatMessages.scrollHeight;
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = chatForm.querySelector("textarea");
    const button = chatForm.querySelector("button");
    const body = input.value.trim();
    if (!body) return;
    button.disabled = true;
    try {
      const response = await fetch(`/api/chat/${chatForm.dataset.friendId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "訊息送出失敗");
      document.querySelector("#emptyChat")?.remove();
      const bubble = document.createElement("div");
      bubble.className = "chat-bubble mine";
      bubble.innerHTML = `<span>${escapeChatHtml(payload.sender_name)}</span><p>${escapeChatHtml(payload.body)}</p>`;
      chatMessages.appendChild(bubble);
      input.value = "";
      chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (error) {
      alert(error.message);
    } finally {
      button.disabled = false;
      input.focus();
    }
  });
}

function escapeChatHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
