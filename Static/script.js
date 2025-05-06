
//AI Chat functionality
function sendMessage() {
    const userInput = document.getElementById("user-input").value;
    if (!userInput.trim()) return;
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML += `<div style="margin-bottom: 10px"><strong>You:</strong> ${userInput}</div>`;
    fetch("/aichat/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userInput })
    })
    .then(response => response.json())
    .then(data => {
        chatBox.innerHTML += `<div><strong>Bot:</strong> ${data.response}</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    });
    document.getElementById("user-input").value = "";
}
document.getElementById("user-input").addEventListener("keypress", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
    }
});

