import React, { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
}

export const ChatBot: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    { id: 'welcome', sender: 'ai', text: 'Hello! I am your technical assistant. How can I help you today?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Create a persistent unique session ID for the backend loop
  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessageText = input.trim();
    setInput('');
    
    // 1. Immediately append the user message to the UI
    const userMessage: Message = {
      id: crypto.randomUUID(),
      sender: 'user',
      text: userMessageText,
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // 2. Fire request to your FastAPI agent backend
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          user_input: userMessageText,
        }),
      });

      if (!response.ok) throw new Error('Network error');

      const data = await response.json();

      // 3. Append the AI Agent response to the UI
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: 'ai',
          text: data.response,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: 'ai',
          text: 'Sorry, I failed to communicate with the server. Please check your backend connection.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto bg-gray-50 border border-gray-200 shadow-md rounded-lg overflow-hidden my-4">
      {/* Header */}
      <div className="bg-slate-800 text-white p-4 flex items-center justify-between">
        <div>
          <h1 className="font-bold text-lg"> Get started with Onboard AI</h1>
          <p className="text-xs text-slate-300">Technical Research & Debug Agent</p>
        </div>
        <div className="h-3 w-3 rounded-full bg-green-400 animate-pulse" />
      </div>

      {/* Message Area */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[75%] p-3 rounded-lg text-sm whitespace-pre-wrap ${
                msg.sender === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none shadow-sm'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        
        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 p-3 rounded-lg text-sm text-gray-500 rounded-bl-none shadow-sm flex items-center space-x-2">
              <span className="font-medium animate-pulse">Agent is thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <form onSubmit={handleSend} className="p-4 bg-white border-t border-gray-200 flex space-x-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a technical or workflow question..."
          className="flex-1 border border-gray-300 rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2 rounded-md transition-colors disabled:opacity-50 text-sm"
        >
          Send
        </button>
      </form>
    </div>
  );
};

