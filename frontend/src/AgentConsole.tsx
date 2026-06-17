import React, { useState } from 'react';
import { useAgentWebSocket } from './useAgentWebSocket';

const AgentConsole = ({ wsUrl, initData }: { wsUrl: string, initData?: any }) => {
  const { messages, isConnected, isWaitingForInput, currentQuestion, sendAnswer, sendConfirm, sendInitData } = useAgentWebSocket(wsUrl);
  const [inputValue, setInputValue] = useState('');
  const [hasSentInit, setHasSentInit] = useState(false);

  React.useEffect(() => {
      if (isConnected && initData && !hasSentInit) {
          sendInitData(initData);
          setHasSentInit(true);
      }
  }, [isConnected, initData, hasSentInit]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() && currentQuestion?.payload.required) return;
    sendAnswer(inputValue);
    setInputValue('');
  };

  return (
    <div className="flex flex-col h-[600px] border rounded-lg bg-slate-50">
      <div className="bg-slate-800 text-white p-3 rounded-t-lg flex justify-between items-center">
        <h3 className="font-semibold">Agent Interactive Session</h3>
        <span className={`text-xs px-2 py-1 rounded ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className="flex flex-col gap-2">
            <div className={`p-3 rounded-lg max-w-[80%] ${
              msg.type === 'error' ? 'bg-red-100 text-red-800' :
              msg.type === 'success' ? 'bg-green-100 text-green-800' :
              msg.type === 'preview' ? 'bg-indigo-50 border border-indigo-200' :
              'bg-white border shadow-sm'
            }`}>
              {msg.type === 'preview' ? (
                <pre className="text-xs overflow-x-auto">{JSON.stringify(msg.payload.entity, null, 2)}</pre>
              ) : (
                <p className="whitespace-pre-wrap text-sm">{msg.payload.message || msg.payload.question}</p>
              )}
            </div>

            {msg.userReply && (
              <div className="self-end bg-blue-600 text-white p-2 px-4 rounded-lg max-w-[80%] text-sm">
                {msg.userReply}
              </div>
            )}
          </div>
        ))}
        {messages.length === 0 && <p className="text-gray-500 text-center mt-10">Waiting for agent...</p>}
      </div>

      {isWaitingForInput && currentQuestion && (
        <div className="p-4 bg-white border-t rounded-b-lg">
          {currentQuestion.type === 'confirm' ? (
            <div className="flex gap-4">
              <button onClick={() => sendConfirm(true)} className="flex-1 bg-green-600 text-white py-2 rounded hover:bg-green-700">Yes</button>
              <button onClick={() => sendConfirm(false)} className="flex-1 bg-red-600 text-white py-2 rounded hover:bg-red-700">No</button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={currentQuestion.payload.required ? "Type your answer..." : "Type answer or leave blank to skip..."}
                className="flex-1 border p-2 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                autoFocus
              />
              <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Send</button>
            </form>
          )}
        </div>
      )}
    </div>
  );
};

export default AgentConsole;
