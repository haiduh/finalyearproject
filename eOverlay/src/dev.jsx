import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
const { ipcRenderer } = window.require('electron');
import './dev.css';

function DevApp() {
  const [input, setInput] = useState('');
  const [logs, setLogs] = useState([]);

  const sendMessage = () => {
    if (input.trim()) {
      // Example of sending a message to the main process
      ipcRenderer.send('dev-message', input);
      setLogs(prev => [...prev, `Sent: ${input}`]);
      setInput('');
    }
  };

  // Listen for responses
  React.useEffect(() => {
    const handleResponse = (_, message) => {
      setLogs(prev => [...prev, `Received: ${message}`]);
    };

    ipcRenderer.on('dev-response', handleResponse);

    return () => {
      ipcRenderer.removeListener('dev-response', handleResponse);
    };
  }, []);

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold mb-4">Developer Console</h1>
      
      <div className="flex mb-4">
        <input
          type="text"
          className="flex-grow p-2 border rounded mr-2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter command..."
        />
        <button 
          onClick={sendMessage}
          className="bg-blue-500 text-white p-2 rounded"
          disabled={!input.trim()}  // Disable button if input is empty
        >
          Send
        </button>
      </div>
      
      <div className="bg-gray-100 p-3 rounded h-64 overflow-auto">
        {logs.length === 0 ? (
          <p className="text-gray-500">No messages yet</p>
        ) : (
          logs.slice(-50).map((log, i) => (  // Keep only the last 50 logs
            <div key={i} className="mb-1">{log}</div>
          ))
        )}
      </div>
    </div>
  );
}

// Modern React 18 rendering
const container = document.getElementById('root');
const root = createRoot(container);
root.render(<DevApp />);
