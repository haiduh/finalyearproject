import React, { useEffect, useRef, useState } from 'react';
const { ipcRenderer } = window.require('electron');

export default function App() {
  const [response, setResponse] = useState("");
  const [prompt, setPrompt] = useState("");
  const [gameName, setGameName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isDetecting, setIsDetecting] = useState(false);
  const [manualEntry, setManualEntry] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [pdfUploaded, setPdfUploaded] = useState(false);
  const [pdfName, setPdfName] = useState("");
  const [isOverlay, setIsOverlay] = useState(false);
  const fileInputRef = useRef(null);
  

  // Function to ask a question to the backend API
  const askQuestion = async (question, gameName, isPdfMode) => {
    try {
      const response = await fetch('http://localhost:8000/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text: question, 
          gameName: gameName,
          isPdfMode: isPdfMode 
        }),
      });
      return await response.json();
    } catch (error) {
      console.error("Connection error details:", error);
      throw error;
    }
  };

  const testConnection = async () => {
    try {
      const response = await fetch('http://localhost:8000/ping');
      const data = await response.json();
      console.log("Connection successful:", data);
      return true;
    } catch (err) {
      console.error("Connection test failed:", err);
      return false;
    }
  };

  // Function to detect the current game from the backend
  const detectGame = async () => {
    if (pdfUploaded) return;
    
    setIsDetecting(true);
    try {
      const response = await fetch('http://localhost:8000/detect-game', {
        method: 'GET',
      });
      const data = await response.json();
      
      if (data && data.gameName && data.gameName.trim() !== "") {
        setGameName(data.gameName);
        setManualEntry(false);
        return data.gameName;
      } else {
        setError("No game detected. You can enter a game name manually.");
        setManualEntry(true);
        return "";
      }
    } catch (err) {
      setError("Error detecting game. You can enter a game name manually.");
      setManualEntry(true);
      return "";
    } finally {
      setIsDetecting(false);
    }
  };

  useEffect(() => {
    if (!pdfUploaded) {
      detectGame();
    }
  }, [pdfUploaded]);

  const handleSubmit = async (e) => {
    e.preventDefault();  
    
    setError("");
    setResponse("");
    setLoading(true);

    if (prompt.trim() === "") {
      setError("Please input a question.");
      setLoading(false);
      return; 
    }

    if (!pdfUploaded && gameName.trim() === "") {
      setError("Please enter a game name.");
      setManualEntry(true);
      setLoading(false);
      return;
    }
    
    const combinedQuestion = `${prompt} ${gameName}`;

    try {
      const data = await askQuestion(
        combinedQuestion, 
        pdfUploaded ? pdfName : gameName, 
        pdfUploaded
      );

      if (data) {
        setResponse(data.response); 
      }
    } catch (err) {
      setError("Error connecting to server");
    } finally {
      setLoading(false);
    }
  };

  // File handling functions
  const handleFileChange = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handlePdfUpload(files[0]);
    }
  };

  const handlePdfUpload = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setUploadStatus("Please select a PDF file.");
      return;
    }
  
    setUploading(true);
    setUploadStatus("Uploading PDF...");
  
    const formData = new FormData();
    formData.append('file', file);
  
    try {
      const response = await fetch('http://localhost:8000/upload-pdf', {
        method: 'POST',
        body: formData,
      });
  
      const data = await response.json();
      
      if (response.ok) {
        setPdfUploaded(true);
        setPdfName(file.name);
        setUploadStatus(`PDF uploaded successfully: ${file.name}`);
        setGameName("");
        setManualEntry(false);
        setError("");
        
        // 🛠️ Reset file input to allow re-uploading the same file
        document.getElementById("pdf-upload-input").value = "";
      } else {
        setUploadStatus(`Upload failed: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      setUploadStatus("Error connecting to server for upload");
    } finally {
      setUploading(false);
    }
  };

  const clearPdf = async () => {
    if (!pdfName) {
      setUploadStatus("No PDF selected to clear.");
      return;
    }
  
    setUploadStatus("Clearing uploaded PDF...");
  
    try {
      const response = await fetch('http://localhost:8000/delete-pdf', {
        method: 'POST',
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pdf_name: pdfName }),
      });
  
      const data = await response.json();
  
      if (response.ok) {
        setPdfUploaded(false);
        setPdfName("");
        setUploadStatus(`PDF cleared successfully.`);
      } else {
        setUploadStatus(`Failed to clear PDF: ${data.error || "Unknown error"}`);
      }
    } catch (err) {
      console.error("Error clearing PDF:", err);
      setUploadStatus("Error connecting to server.");
    }
  };
  
  

  useEffect(() => {
    // Add the event listener
    ipcRenderer.on('overlay-toggled', (_, state) => {
      setIsOverlay(state);
    });
    
    // Clean up function to remove the listener when component unmounts
    return () => {
      ipcRenderer.removeListener('overlay-toggled', (_, state) => {
        setIsOverlay(state);
      });
    };
  }, []); // Empty dependency array means this runs once on mount

  const toggleOverlay = () => {
    ipcRenderer.send('toggle-overlay');
  };

  const triggerFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };
  
  
  return (
    <div className="text-white p-4">
      <div className={'font-bold text-white drag-handle mb-4'}>&#1006;</div>
      <div>
        <button onClick={toggleOverlay}>
        {isOverlay ? 'Exit Overlay Mode' : 'Enter Overlay Mode'}
      </button>
      </div>
      
      <div className="bg-zinc-900 rounded-lg p-4 shadow-lg">
        {pdfUploaded ? (
          <div className="pdf-info mb-4">
            <span>Current PDF: {pdfName}</span>
            <button 
              onClick={clearPdf} 
              className="bg-red-500 text-white p-1 rounded ml-2"
            >
              Clear PDF
            </button>
          </div>
        ) : (
          <div className="game-info mb-4">
            {isDetecting ? (
              <span>Detecting game...</span>
            ) : (
              <>
                <span>Current game: {gameName || "Unknown"}</span>
                <button 
                  onClick={detectGame} 
                  className="bg-blue-500 text-white p-1 rounded mx-2"
                  disabled={isDetecting}
                >
                  Refresh
                </button>
                <button
                  onClick={() => setManualEntry(!manualEntry)}
                  className="bg-green-500 text-white p-1 rounded"
                >
                  {manualEntry ? "Hide Manual Entry" : "Enter Manually"}
                </button>
              </>
            )}
          </div>
        )}

        {!pdfUploaded && manualEntry && (
          <div className="mb-4">
            <input
              type="text"
              value={gameName}
              onChange={(e) => setGameName(e.target.value)}
              placeholder="Enter game name manually..."
              className="w-full p-2 mb-2 border rounded bg-zinc-800 text-white"
            />
          </div>
        )}

        <div className="mb-4">
          <button
            onClick={triggerFileInput}
            className="bg-purple-500 text-white p-2 rounded w-full"
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : pdfUploaded ? 'Upload Different PDF' : 'Upload PDF'}
          </button>
          <input
            id="pdf-upload-input" 
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf"
            style={{ display: 'none' }}
          />
          {uploadStatus && <p className="mt-2 text-sm">{uploadStatus}</p>}
        </div>

        <form onSubmit={handleSubmit} className="mb-4">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={pdfUploaded ? "Ask questions about your PDF" : "Ask for help..."}
            className="w-full p-2 mb-2 border rounded bg-zinc-800 text-white"
          />
          <button 
            type="submit" 
            className="bg-blue-500 text-white p-2 rounded w-full flex items-center justify-center"
            disabled={loading}
          >
            {loading ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Thinking...</span>
              </>
            ) : 'Submit'}
          </button>
        </form>

        {error && <p className="text-red-500 mb-4">{error}</p>}

        <div className="response-container bg-zinc-800 rounded-lg p-4">
          <div className="flex justify-between items-center mb-2">
            <span className="font-bold text-xl">Response</span>
            {response && (
              <button onClick={() => setResponse('')} className="bg-red-500 text-white p-1 rounded text-sm">
                Clear
              </button>
            )}
          </div>
          <div className="response-content p-3 rounded-lg bg-zinc-700 min-h-20">
            {response ? (
              <div className="response-text">
                <p>{response}</p>
              </div>
            ) : (
              <p className="text-gray-400">Your answer will appear here...</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}