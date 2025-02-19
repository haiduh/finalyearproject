import React, { useState } from 'react';
import mockData from './mockData.json';
import './css/overlay.css';

// Define the type for the mock data
interface MockData {
  tutorials: {
    [key: string]: string; // This will allow any string key
  };
}

function App() {
  const [response, setResponse] = useState("");
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState(""); // To store error messages

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();  

    // clears the error and response before submission
    setError("");
    setResponse("");

    // Check if input is empty
    if (prompt.trim() === "") {
      setError("Input cannot be empty!");
      return; 
    }

    try {

      //json server for testing the API
      const apiResponse = await fetch(`http://localhost:8000/tutorials/${prompt}`);
      const data = await apiResponse.json();

      if (data) {
        setResponse(data);
      } else {
        setResponse("No tutorial found.");
      }
    } catch (error) {
      const mockDataTyped: MockData = mockData; 

      // Check if the prompt exists in mock data
      if (mockDataTyped.tutorials[prompt]) {
        setResponse(mockDataTyped.tutorials[prompt]);
      } else {
        setResponse("No tutorial found (offline).");
      }
    }
  };

  return (
    <div className="overlay">
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ask for help..."
        />
        <button type="submit">Submit</button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <p>{response}</p>
    </div>
  );
}

export default App;
