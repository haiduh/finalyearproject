# AI-Powered In-Game Assistant

An AI-powered in-game assistant that provides real-time, context-aware assistance to players. The system leverages a Retrieval-Augmented Generation (RAG) pipeline, large language models (LLMs), and dynamic data fetching to deliver accurate and relevant in-game guidance without disrupting the player's experience.

## Features

- **Dynamic Assistance**: Provides real-time responses to player queries, fetching data dynamically from in-game datasets or external sources.
- **Cross-Game Support**: Easily adaptable to multiple games by uploading structured datasets (JSON, wiki formats, etc.) with minimal effort.
- **Overlay Integration**: An Electron-based overlay displays answers directly in the game without interrupting gameplay.
- **Natural Language Processing (NLP)**: Utilizes semantic search and LLM-powered reasoning to refine responses and ensure relevance.
- **Developer Tools**: Includes an interface for developers to upload datasets and integrate the system into new games.

## Installation

### Prerequisites

- **Node.js** (v16 or later) for Electron
- **Python** (v3.8 or later)
- **Pip** (Python package manager)
- **Pinecone account** (for vector database integration)

### Step 1: Clone the repository

```bash
git clone https://github.com/yourusername/ai-in-game-assistant.git
cd ai-in-game-assistant
```

### Step 2: Install Backend (Python Dependencies)

In the backend/ folder:

```bash
cd backend
pip install -r requirements.txt
```

### Step 3: Install Frontend (Electron & Node.js Dependencies)

In the frontend/ folder:

```bash
cd frontend
npm install
```

### Step 4: Setup Pinecone (or alternative vector database)

1. Sign up for a Pinecone account.
2. Follow the documentation to get your API Key.
3. In the backend/config.py file, replace the placeholder with your API key.

### Step 5: Run the Project

Start Backend:

```bash
cd backend
python app.py
```

Start Frontend (Electron):

```bash
cd frontend
npm start
```

The application should now open an Electron window where you can interact with the assistant in the game.

## Usage

### In-Game Interaction:

1. Press F2 to open the assistant overlay.
2. Ask a question using natural language (e.g., "Where is the Silver Sword?").
3. The assistant will display the response directly in the game.

### Developer Tools:

1. Press F3 to open the developer tools.
2. Upload a structured dataset (in JSON format) for a new game to enable querying.
3. The system will automatically integrate and make the new dataset available for player queries.

## Example Datasets

You can find example game datasets in the `datasets/` folder. These datasets are structured in JSON format, where each entry represents a game-specific element (e.g., items, quests, locations). Developers can modify or add to these datasets as needed.

## Contributing

Feel free to fork this repository and make improvements or add new features. If you have suggestions or find any issues, open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Pinecone for vector database service
- Electron for seamless cross-platform desktop app development
- OpenAI GPT models for natural language processing
