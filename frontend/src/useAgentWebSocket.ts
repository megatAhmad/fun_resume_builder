import { useState, useEffect, useRef } from 'react';

type Message = {
  id: number;
  type: 'question' | 'confirm' | 'info' | 'error' | 'success' | 'preview';
  payload: any;
  userReply?: string;
};

export const useAgentWebSocket = (url: string) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isWaitingForInput, setIsWaitingForInput] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState<Message | null>(null);

  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    ws.current = new WebSocket(url);

    ws.current.onopen = () => setIsConnected(true);

    ws.current.onclose = () => {
      setIsConnected(false);
      setIsWaitingForInput(false);
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const newMsg = { ...data, id: Date.now() };

      setMessages(prev => [...prev, newMsg]);

      if (data.type === 'question' || data.type === 'confirm') {
        setIsWaitingForInput(true);
        setCurrentQuestion(newMsg);
      }
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [url]);

  const sendAnswer = (answer: string) => {
    if (!ws.current || !currentQuestion) return;

    setMessages(prev =>
      prev.map(m => m.id === currentQuestion.id ? { ...m, userReply: answer } : m)
    );

    ws.current.send(JSON.stringify({ type: 'answer', payload: { answer } }));
    setIsWaitingForInput(false);
    setCurrentQuestion(null);
  };

  const sendConfirm = (answer: boolean) => {
    if (!ws.current || !currentQuestion) return;

    setMessages(prev =>
      prev.map(m => m.id === currentQuestion.id ? { ...m, userReply: answer ? 'Yes' : 'No' } : m)
    );

    ws.current.send(JSON.stringify({ type: 'confirm_answer', payload: { answer } }));
    setIsWaitingForInput(false);
    setCurrentQuestion(null);
  };

  const sendInitData = (payload: any) => {
      if (!ws.current) return;
      ws.current.send(JSON.stringify({ type: 'init', payload }));
  }

  return {
    messages,
    isConnected,
    isWaitingForInput,
    currentQuestion,
    sendAnswer,
    sendConfirm,
    sendInitData
  };
};
