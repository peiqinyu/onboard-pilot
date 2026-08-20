// Define interface for request and response layout
interface ChatResponse {
  response: string;
}

class AgentChatService {
  private apiBaseUrl: string;
  private sessionId: string;

  constructor(apiBaseUrl: string) {
    this.apiBaseUrl = apiBaseUrl;
    // Generate a simple unique ID for this specific UI conversation session
    this.sessionId = crypto.randomUUID(); 
  }

  /**
   * Sends the user message to the backend agent server
   */
  async sendMessage(userInput: string): Promise<string> {
    try {
      const response = await fetch(`${this.apiBaseUrl}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: this.sessionId,
          user_input: userInput,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: ChatResponse = await response.json();
      return data.response;
    } catch (error) {
      console.error("Failed to communicate with AI Agent:", error);
      return "Error: Could not connect to the backend agent.";
    }
  }
}

// --- Usage Example in your UI component layer ---
const chatService = new AgentChatService("http://localhost:8000");

async function handleSendMessageClick() {
  const inputElement = document.getElementById("chat-input") as HTMLInputElement;
  const userText = inputElement.value;
  
  if (!userText.trim()) return;

  // Append user's text immediately to the UI window list
  appendMessageToUI("User", userText);
  inputElement.value = ""; 

  // Call Python Backend API
  const aiAnswer = await chatService.sendMessage(userText);
  
  // Render agent output on screen
  appendMessageToUI("AI Agent", aiAnswer);
}
