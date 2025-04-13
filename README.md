# AI-Powered In-Game Assistant

An AI-powered in-game assistant that provides real-time, context-aware assistance to players. The system leverages a Retrieval-Augmented Generation (RAG) pipeline, large language models (LLMs), and dynamic data fetching to deliver accurate and relevant in-game guidance without disrupting the player's experience.

![implementation](https://github.com/user-attachments/assets/ccaaf314-b2de-4b45-b2f4-452d1d4391dc)


## Features

- **Dynamic Assistance**: Provides real-time responses to player queries, fetching data dynamically from in-game datasets or external sources.
- **Cross-Game Support**: Easily adaptable to multiple games by uploading structured datasets (JSON, wiki formats, etc.) with minimal effort.
- **Overlay Integration**: An Electron-based overlay displays answers directly in the game without interrupting gameplay.
- **Natural Language Processing (NLP)**: Utilises semantic search and LLM-powered reasoning to refine responses and ensure relevance.
- **Developer Tools**: Includes an interface for developers to upload datasets and integrate the system into new games.

## Technology Stack

- **Frontend**: Electron with React for cross-platform desktop application development
  - Enables seamless in-game overlay that doesn't interrupt the gaming experience
  - React components provide responsive UI elements for both players and developers
  - Custom React hooks manage state and API communication with the backend
- **Backend**: Python with Flask API
  - Handles RAG pipeline processing and LLM integration
  - Manages vector database connections and query processing
- **Vector Database**: Pinecone for efficient similarity searches
- **LLM Integration**: Connects to various large language models for natural language understanding

## Installation

### Prerequisites

- **Node.js** (v16 or later) for Electron
- **Python** (v3.8 or later)
- **Pip** (Python package manager)
- **Pinecone account** (for vector database integration)

### Step 1: Clone the repository

```bash
git clone https://github.com/haiduh/finalyearproject.git
cd "AI Assistant"
```

### Step 2: Install Frontend (Electron & React Dependencies)

In the frontend/ folder:

```bash
cd "1. frontend"
npm install
```

### Step 3: Install Backend (Python Dependencies)

In the backend/ folder:

```bash
cd "2. backend"
pip install -r requirements.txt
```

### Step 4: Setup Pinecone (or alternative vector database)

1. Sign up for a Pinecone account.
2. Follow the documentation to get your API Key.
3. In the backend/.env file, replace the placeholder with your API key.

### Step 5: Run the Project

Start Frontend (Electron + React):

```bash
cd "1. frontend"
npm start
```

Start Backend:

```bash
cd "2. backend"
python backend.py
```

The application should now open an Electron window with the React UI where you can interact with the assistant in the game.

## Usage

### In-Game Interaction:

1. Press F2 to open the assistant overlay.
2. Ask any game-related query (e.g., "What is the Y level for finding diamonds in Minecraft?").
3. The assistant will display the response directly in the overlay UI.

### Developer Tools:

1. Press F3 to open the developer tools.
2. Upload a structured dataset (in JSON format) for a new game to enable querying.
3. The system will automatically integrate and make the new dataset available for player queries.

## Frontend Architecture

The frontend is built with Electron and React to provide a seamless overlay experience:

- **Main Process**: Handles the Electron window creation, game overlay integration, and IPC communication
- **Renderer Process**: Contains the React application that renders the UI components

## Example Datasets

You can find example game datasets in the `3. datasets/` folder. Developers can modify or add to these datasets as needed.

## Contributing

Feel free to fork this repository and make improvements or add new features. If you have suggestions or find any issues, open an issue or submit a pull request.

## Acknowledgments

- Pinecone for vector database service
- Electron and React for seamless cross-platform desktop app development
- OpenAI GPT models for natural language processing
