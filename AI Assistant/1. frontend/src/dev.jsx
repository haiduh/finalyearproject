import React, { useState, useRef} from 'react';
import { createRoot } from 'react-dom/client';
import './dev.css';

function DevApp() {

  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [dataUploaded, setDataUploaded] = useState(false);
  const [dataName, setDataName] = useState("");
  const [dataType, setDataType] = useState("");
  const [importType, setImportType] = useState("json");
  const [url, setUrl] = useState("");
  const [showUrlInput, setShowUrlInput] = useState(false);
  
  const fileInputRef = useRef(null);

  const triggerFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleDataUpload(files[0]);
    }
  };

  const handleDataUpload = async (file) => {
    if (!file) {
      setUploadStatus("No file selected.");
      return;
    }
  
    // Check file extension matches selected import type
    const fileExt = file.name.split('.').pop().toLowerCase();
    if (
      (importType === "json" && fileExt !== "json") ||
      (importType === "csv" && fileExt !== "csv") ||
      (importType === "pdf" && fileExt !== "pdf") ||
      (importType === "markdown" && !["md", "markdown"].includes(fileExt))
    ) {
      setUploadStatus(`File type doesn't match selected import type (${importType}).`);
      return;
    }
  
    setUploading(true);
    setUploadStatus(`Uploading ${importType.toUpperCase()} file...`);
  
    const formData = new FormData();
    formData.append("file", file);
    formData.append("type", importType);
  
    try {
      // Correctly set the endpoint
      const endpoint = "http://localhost:8000/upload-data";
  
      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });
  
      const data = await response.json();
  
      if (response.ok) {
        setDataUploaded(true);
        setDataName(file.name);
        setDataType(importType.toUpperCase());
        setUploadStatus(`${importType.toUpperCase()} uploaded successfully: ${file.name}`);
  
        // Reset file input to allow re-uploading the same file
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      } else {
        setUploadStatus(`Upload failed: ${data.error || "Unknown error"}`);
      }
    } catch (err) {
      console.error("Error uploading data:", err);
      setUploadStatus("Error connecting to server for upload");
    } finally {
      setUploading(false);
    }
  };
  

  const importFromUrl = async () => {
    if (!url.trim()) {
      setUploadStatus("Please enter a valid URL.");
      return;
    }
    
    setUploading(true);
    setUploadStatus("Importing data from URL...");
    
    try {
      const response = await fetch('http://localhost:8000/import-from-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });
      
      // Parse the response JSON
      const data = await response.json();
      
      // Check if the response is not OK (status code is not in 200-299 range)
      if (!response.ok) {
        // Use the error message from the backend or provide a generic error
        const errorMessage = data.message || data.error || `URL import failed with status ${response.status}`;
        setUploadStatus(`Error: ${errorMessage}`);
        setUploading(false);
        return;
      }
      
      setDataUploaded(true);
      setDataName(new URL(url).hostname);
      setDataType('URL');
      setUploadStatus(`URL data imported successfully from: ${url}`);
      setUrl("");
      setShowUrlInput(false); // Hide URL input after successful import
    } catch (err) {
      console.error("Error importing from URL:", err);
      
      // Provide a more detailed error message
      const errorMessage = err instanceof TypeError 
        ? "Network error. Please check your connection." 
        : "Unexpected error during URL import";
      
      setUploadStatus(`Error: ${errorMessage}`);
    } finally {
      setUploading(false);
    }
  };


  const clearData = async () => {
    if (!dataName) {
      setUploadStatus("No data selected to clear.");
      return;
    }
  
    setUploadStatus("Clearing uploaded data...");
  
    try {
      // Correctly set the endpoint
      const endpoint = "http://localhost:8000/delete-data"; 
  
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          file_name: dataName,
          type: dataType.toLowerCase(),
        }),
      });
  
      const data = await response.json();
  
      if (response.ok) {
        setDataUploaded(false);
        setDataName("");
        setDataType("");
        setUploadStatus(""); 
        
        // Reset URL input state
        setUrl("");
        setShowUrlInput(false);
      } else {
        setUploadStatus(`Failed to clear data: ${data.error || "Unknown error"}`);
      }
    } catch (err) {
      console.error("Error clearing data:", err);
      setUploadStatus("Error connecting to server.");
    }
  };
  

  return (
    <div className="dev-container">
      <div className="w-full flex justify-center items-center drag-handle py-2">
        <div className="w-20 h-[3px] bg-white mb-4"></div>
      </div>
      <h1 className="text-xl font-bold mb-4 text-white">Developer Console</h1>
      <div className="mb-4 p-4 border rounded bg-slate-700">
        <h2 className="text-lg font-semibold mb-3 text-white">Game Data Import</h2>
        
        {dataUploaded ? (
          <div className="data-info mb-4 text-white">
            <span>Current Data: {dataName} ({dataType})</span>
            <button 
              onClick={clearData} 
              className="bg-red-500 text-white p-1 rounded ml-2"
            >
              Clear Data
            </button>
          </div>
        ) : (
          <p className="text-white mb-3">No data currently imported.</p>
        )}
        
        <div className="mb-2">
          <select 
            value={importType} 
            onChange={(e) => {
              setImportType(e.target.value);
              setUploadStatus(""); // Clear status when import type changes
            }}
            className="p-2 border rounded mr-2"
          >
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
            <option value="pdf">PDF</option>
            <option value="markdown">Markdown</option>
            <option value="url">URL</option>
          </select>
          
          {importType !== 'url' && (
            <button
              onClick={triggerFileInput}
              className="bg-purple-500 text-white p-2 rounded"
              disabled={uploading}
            >
              {uploading ? 'Importing...' : dataUploaded ? 'Import Different Data' : 'Import Data'}
            </button>
          )}
          
          {importType === 'url' && (
            <div className="mt-2">
              {(!dataUploaded || showUrlInput) && (
                <div>
                  <input
                    type="text"
                    placeholder="Enter URL to import..."
                    className="p-2 border rounded mr-2 w-full"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                  <button
                    onClick={importFromUrl}
                    className="bg-purple-500 text-white p-2 rounded mt-2"
                    disabled={!url.trim() || uploading}
                  >
                    Import from URL
                  </button>
                </div>
              )}
              
              {dataUploaded && !showUrlInput && (
                <button
                  onClick={() => setShowUrlInput(true)}
                  className="bg-purple-500 text-white p-2 rounded"
                >
                  Import Different URL
                </button>
              )}
            </div>
          )}
        </div>
        
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept={
            importType === 'json' ? '.json' : 
            importType === 'csv' ? '.csv' : 
            importType === 'pdf' ? '.pdf' : 
            importType === 'markdown' ? '.md,.markdown' : 
            '*'
          }
          style={{ display: 'none' }}
        />
        {uploadStatus && <p className="mt-2 text-sm text-white">{uploadStatus}</p>}
      </div>
    </div>
  );
}

// Rendering for DevApp
const container = document.getElementById('root');
const root = createRoot(container);
root.render(<DevApp />);