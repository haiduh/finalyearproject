import React, { useState, useEffect, useRef } from 'react';
import './css/overlay.css';

function App() {
  const [response, setResponse] = useState("");
  const [prompt, setPrompt] = useState("");
  const [gameName, setGameName] = useState(""); // Game detected or entered by user
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isDetecting, setIsDetecting] = useState(false);
  const [manualEntry, setManualEntry] = useState(false); // Controls whether to show manual input
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [pdfUploaded, setPdfUploaded] = useState(false);
  const [pdfName, setPdfName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Function to ask a question to the backend API
  const askQuestion = async (question: string, gameName: string, isPdfMode: boolean) => {
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
  };

  // Function to detect the current game from the backend
  const detectGame = async () => {
    if (pdfUploaded) return; // Don't detect game if in PDF mode
    
    setIsDetecting(true);
    try {
      const response = await fetch('http://localhost:8000/detect_game', {
        method: 'GET',
      });
      const data = await response.json();
      
      if (data && data.gameName && data.gameName.trim() !== "") {
        setGameName(data.gameName);
        setManualEntry(false); // Hide manual entry if we detected a game
        return data.gameName;
      } else {
        setError("No game detected. You can enter a game name manually.");
        setManualEntry(true); // Show manual entry if no game detected
        return "";
      }
    } catch (err) {
      setError("Error detecting game. You can enter a game name manually.");
      setManualEntry(true); // Show manual entry if detection failed
      return "";
    } finally {
      setIsDetecting(false);
    }
  };

  // Detect game on component mount
  useEffect(() => {
    if (!pdfUploaded) {
      detectGame();
    }
  }, [pdfUploaded]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();  
    
    setError("");
    setResponse("");
    setLoading(true);

    if (prompt.trim() === "") {
      setError("Please input a question.");
      setLoading(false);
      return; 
    }

    // Check if we need game name (not needed if PDF is uploaded)
    if (!pdfUploaded) {
      const currentGame = gameName.trim();
      if (currentGame === "") {
        setError("Please enter a game name.");
        setManualEntry(true);
        setLoading(false);
        return;
      }
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

  const handleManualRefresh = () => {
    detectGame();
  };

  // Toggle manual entry mode
  const toggleManualEntry = () => {
    setManualEntry(!manualEntry);
  };

  // Function to handle PDF upload
  const handlePdfUpload = async (file: File) => {
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
        // Clear game detection-related states
        setGameName("");
        setManualEntry(false);
        setError("");
      } else {
        setUploadStatus(`Upload failed: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      setUploadStatus("Error connecting to server for upload");
    } finally {
      setUploading(false);
    }
  };

  // Function to clear PDF and return to game mode
  const clearPdf = () => {
    setPdfUploaded(false);
    setPdfName("");
    setUploadStatus("");
    // Re-detect game
    detectGame();
  };

  // Function to trigger file input click when button is clicked
  const triggerFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // Function to handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handlePdfUpload(files[0]);
    }
  };

  return (
    <div className="overlay">
      {pdfUploaded ? (
        <div className="pdf-info">
          <span>Current PDF: {pdfName}</span>
          <button 
            onClick={clearPdf} 
            className="clear-pdf-button bg-red-500 text-white p-1 rounded ml-2"
          >
            Clear PDF
          </button>
        </div>
      ) : (
        <div className="game-info">
          {isDetecting ? (
            <span>Detecting game...</span>
          ) : (
            <>
              <span>Current game: {gameName || "Unknown"}</span>
              <button 
                onClick={handleManualRefresh} 
                className="refresh-button bg-blue-500 text-white p-1 rounded mr-2"
                disabled={isDetecting}
              >
                Refresh
              </button>
              <button
                onClick={toggleManualEntry}
                className="manual-button bg-green-500 text-white p-1 rounded"
              >
                {manualEntry ? "Hide Manual Entry" : "Enter Manually"}
              </button>
            </>
          )}
        </div>
      )}

      {!pdfUploaded && manualEntry && (
        <div className="manual-entry mt-2">
          <input
            type="text"
            value={gameName}
            onChange={(e) => setGameName(e.target.value)}
            placeholder="Enter game name manually..."
            className="w-full p-2 mb-2 border rounded"
          />
        </div>
      )}

      <div className="pdf-upload mt-4">
        <button
          onClick={triggerFileInput}
          className="bg-purple-500 text-white p-2 rounded w-full"
          disabled={uploading}
        >
          {uploading ? 'Uploading...' : pdfUploaded ? 'Upload Different PDF' : 'Upload PDF'}
        </button>
        <input 
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".pdf"
          style={{ display: 'none' }}
        />
        {uploadStatus && <p className="mt-2">{uploadStatus}</p>}
      </div>

      <form onSubmit={handleSubmit} className="mt-4">
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={pdfUploaded ? "Ask questions from your own game" : "Ask for help..."}
          className="w-full p-2 mb-2 border rounded"
        />
        <button 
          type="submit" 
          className="bg-blue-500 text-white p-2 rounded w-full"
          disabled={loading}
        >
          {loading ? 'Loading...' : 'Submit'}
        </button>
      </form>
      {error && <p style={{ color: 'red' }} className="mt-2">{error}</p>}
      <div className="response-container mt-4">
        <div className="response-header">
          <span className="font-bold text-xl">Response</span>
          <div className="response-close-button">
            {/* Optional close button to clear responses */}
            <button onClick={() => setResponse('')} className="bg-red-500 text-white p-1 rounded">
              Clear
            </button>
          </div>
        </div>
        <div className="response-content mt-2 p-4 rounded-lg bg-gray-100 shadow-lg">
          {response ? (
            <div className="response-text">
              {/* Example of formatting the response with highlights */}
              <p>{response}</p>
            </div>
          ) : (
            <p className="text-gray-500">Your answer will appear here...</p>
          )}
        </div>
        </div>

    </div>
  );
}

export default App;