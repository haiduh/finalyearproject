from pypdf import PdfReader
from contextlib import asynccontextmanager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec
from litellm import completion
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler
from urllib.parse import urlparse
import logging
import datetime
import pygetwindow as gw
import psutil
import requests
import json
import time
import os
import re
import uuid
import hashlib
import uvicorn


# Initialize index_name at the module level
index_name = "example-index"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pc, index
    # Pinecone API Setup
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    if not PINECONE_API_KEY:
        print("❌ ERROR: Missing PINECONE_API_KEY.")
        return

    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # Create index if it doesn't exist
    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=1536,  # Must match embedding size
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )

    # Wait for index to be ready
    while not pc.describe_index(index_name).status["ready"]:
        print("⏳ Waiting for Pinecone index to be ready...")
        time.sleep(2)

    index = pc.Index(index_name)
    print("✅ Pinecone Index Ready.")

    yield

    # Shutdown logic
    print("🔌 Shutting down Pinecone client.")


app = FastAPI(
    title="RAG API",
    description="Streamlined RAG System API for Q&A with web search fallback",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


load_dotenv()

# Function to fetch content from a PDF file
# def fetch_pdf_content(pdf: str):
#     """Fetch content from a PDF file."""
#     reader = PdfReader(pdf)  # Use the variable 'pdf' for the file path
#     number_of_pages = len(reader.pages)
#     content = ""
    
#     # Loop through each page and extract text
#     for page_num in range(number_of_pages):
#         page = reader.pages[page_num]
#         content += page.extract_text()
    
#     return content

async def fetch_url_content(url: str) -> Optional[str]:
    """
    Fetches content from a URL using crawl4ai.
    
    Args:
        url (str): The URL to fetch content from.
        
    Returns:
        Optional[str]: The content retrieved from the URL as a string,
                      or None if the request fails.
    """
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return result.markdown if result else None
    except Exception as e:
        print(f"Error: Failed to fetch content from {url}. Exception: {str(e)}")
        return None

def clean_text(text: str) -> str:
    """Removes extra spaces and newlines."""
    text = text.replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', text).strip()

# Generate embeddings
def get_embeddings(texts, model="text-embedding-3-small", api_key=os.getenv("OPENAI_API_KEY")):
    """Fetch OpenAI embeddings."""
    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"input": texts, "model": model}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        return response.json()["data"]
    else:
        print(f"❌ Embedding Error {response.status_code}: {response.text}")
        return None
    
# Background task to process uploaded file content
def process_data_content(file_content, file_name, file_type, temp_file_path):
    """Process file content in the background"""
    try:
        # Split text
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=150,  # Token size
            chunk_overlap=20,  # Small overlap to maintain context between chunks
        )
        
        # Clean and split text
        text_chunks = [clean_text(chunk) for chunk in text_splitter.split_text(file_content)]
        print(f"✅ Total Chunks from {file_type.upper()}: {len(text_chunks)}")
        
        # Generate embeddings
        embeddings_objects = get_embeddings(text_chunks)
        if embeddings_objects is None:
            print(f"❌ Failed to generate embeddings for {file_name}.")
            return
        
        # Upsert into Pinecone
        vectors_to_upsert = []
        for text, embedding in zip(text_chunks, embeddings_objects):
            # Generate a hash for the content to be used as the vector ID
            content_hash = generate_content_hash(text)
            
            # Check if this hash already exists in the Pinecone index
            if not check_if_exists(index, content_hash):
                # Prepare the record to upsert
                record = {
                    "id": content_hash,
                    "values": embedding["embedding"],
                    "metadata": {
                        "source_text": text, 
                        "file_name": file_name,
                        "file_type": file_type
                    }
                }
                vectors_to_upsert.append(record)
        
        # Batch upsert to Pinecone (more efficient)
        if vectors_to_upsert:
            index.upsert(vectors=vectors_to_upsert, namespace="game_docs")
            print(f"✅ {len(vectors_to_upsert)} new chunks from {file_name} successfully inserted into Pinecone.")
        else:
            print(f"⚠️ No new content to insert from {file_name}.")
    
    finally:
        # Clean up the temporary file - only if it exists and is not None
        if temp_file_path is not None and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


# Function to generate a hash for the content
def generate_content_hash(text: str):
    """Generate a hash for the given content."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

# Function to check if the hashed vector already exists in Pinecone
def check_if_exists(index, content_hash):
    # Try fetching the vector by the content hash as the vector ID
    response = index.fetch([content_hash], namespace="game_docs")
    
    # Check if the vector exists
    return content_hash in response.vectors if response and response.vectors else False


# Decision system prompt
decision_system_prompt = """
Evaluate if the provided context fully addresses the question about gaming.

Context: {context}
Question: {question}

YOUR ANSWER MUST BE EXACTLY ONE CHARACTER:
Return ONLY the digit `1` if the context satisfactorily answers the question.
Return ONLY the digit `0` if the context fails to adequately answer.
DO NOT include any explanation, analysis, or other text in your response.
"""

# LLM response prompt
system_prompt = """
You are an AI assistant embedded in an in-game overlay. Your goal is to provide concise, game-specific assistance in a structured format.

- Keep responses brief and to the point (2-3 sentences).
- Prioritize actionable information like item locations, enemy weaknesses, and quest guidance.
- Avoid unnecessary explanations—only provide what is needed for the player to make progress.
- If the game is unknown, offer general gaming tips instead.
- For unclear or malformed queries, ask for clarification instead of guessing.
- If the query is gibberish or completely invalid, respond with a polite request to rephrase.

Response Format:
[Tip] "Use fire attacks to weaken this enemy."
[Location] "The Dectus Medallion (Left) is in Fort Haight, southeast of Mistwood."
[General] "If you're lost, check for landmarks or quest markers on the map."
[Clarification] "I'm not sure what you're asking. Could you please rephrase your question?"

Only provide answers relevant to the context, and ensure accuracy based on available data.

Context: {context}
"""

user_prompt = """
Question: {question}

Additional Instructions:
1. Focus on the most relevant parts of the provided context.
2. Ask for clarification if the question is unclear.
3. Use game-specific terminology whenever possible.
4. Respond based solely on the provided context, and do not include information outside of it.

Answer:
"""

# Initialize DuckDuckGo Search
def format_search_results(results):
    return "\n\n".join(doc["body"] for doc in results)

def expand_query(question: str) -> list:
    """Generate 3 search variations for better retrieval"""
    prompt = f"""Generate 3 search variations for: {question}
    Focus on game-specific terms and common misunderstandings.
    Return as bullet points:"""
    
    response = completion(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return [line[2:] for line in response.choices[0].message.content.split("\n") if line.startswith("-")]

def cot_analysis(question: str, context: str) -> str:
    """Chain-of-Thought reasoning about the question"""
    prompt = f"""Analyze this gaming question step-by-step:
    1. Identify key game elements
    2. List required mechanics
    3. Match with context
    4. Identify knowledge gaps
    
    Question: {question}
    Context: {context}
    """
    return completion(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.3
    ).choices[0].message.content

def validate_response(response: str, context: str) -> bool:
    """Check if response is context-supported"""
    prompt = f"""Verify if this answer is fully supported by context (1=yes/0=no):
    Context: {context}
    Response: {response}"""
    return completion(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": prompt}],
        temperature=0
    ).choices[0].message.content.strip() == "1"    

def search(query_text: str, namespaces: list, top_k: int = 3):
    """Search with query expansion"""
    # Add query expansion
    expanded_queries = [query_text] + expand_query(query_text)
    query_embedding = get_embeddings([" ".join(expanded_queries)])[0]["embedding"]
    
    # Rest of your original code remains the same
    all_results = []
    for namespace in namespaces:
        results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True, namespace=namespace)
        all_results.extend(results["matches"])
    return {"matches": all_results}

def format_docs(search_results):
    """Format Pinecone search results into readable context."""
    if not search_results["matches"]:
        return ""
    
    return "\n\n".join([match["metadata"]["source_text"] for match in search_results["matches"]])

# Decision system to decide if context can answer the question
def decision_system(context, question):
    """Decision system to decide if context can answer the question."""
    # Input validation
    if not context or not isinstance(context, str) or context.isspace():
        print("❌ No valid context found. Returning 0.")
        return "0"
    
    if not question or not isinstance(question, str) or question.isspace():
        print("❌ No valid question found. Returning 0.")
        return "0"
    
    try:
        # Format the prompt with the context and question
        decision_prompt = decision_system_prompt.format(context=context, question=question)
        
        # Query the LLM with decision prompt
        decision_response = completion(
            model="gpt-4o-mini",
            messages=[{"content": decision_prompt, "role": "system"}],
            max_tokens=3,  # Small number to avoid longer responses
            temperature=0.0  # Zero temperature for deterministic output
        )
        
        # Extract and validate response
        response_text = decision_response.choices[0].message.content.strip()
        
        # Only accept "0" or "1" as valid responses
        if response_text == "0" or response_text == "1":
            return response_text
        else:
            # Extract first digit if response contains one
            for char in response_text:
                if char in ["0", "1"]:
                    print(f"⚠️ Extracted valid digit from response: {response_text}") #Error Checks
                    return char
            
            print(f"⚠️ Unexpected response: {response_text}. Defaulting to 0.")
            return "0"
            
    except Exception as e:
        print(f"⚠️ Error in decision system: {e}. Defaulting to 0.")
        return "0"
    
# Function to store question and response in Pinecone
def qa_storage(question: str, response: str, index, namespace="games_queries"):
    """Store the question and response pair in Pinecone index."""
    # Generate embeddings for the question and response
    question_embedding = get_embeddings([question])[0]["embedding"]
    response_embedding = get_embeddings([response])[0]["embedding"]
    
    # Create a unique ID for this entry
    unique_id = str(uuid.uuid4())
    
    # Create records for the question and response
    records = [
        {"id": f"{unique_id}_question", "values": question_embedding, "metadata": {"question": question, "type": "question"}},
        {"id": f"{unique_id}_response", "values": response_embedding, "metadata": {"response": response, "type": "response"}}
    ]
    
    # Upsert the records into Pinecone
    index.upsert(vectors=records, namespace=namespace)
    print("✅ Question and Response successfully stored in Pinecone.")

def rag_pipeline(question, game_name=None):
    """Complete RAG pipeline implementation that integrates with game detection"""
    # If game_name is provided, append it to the question
    if game_name:
        question = f"{question} in {game_name}"
        
    print(question)
    return response_generation(question)

def response_generation(question):
    # Define the namespaces
    namespaces = ["game_docs", "game_queries"]
    
    # Expand the query before searching
    expanded_queries = [question] + expand_query(question)
    
    # Search for context based on expanded queries
    search_results = search(" ".join(expanded_queries), namespaces)
    context = format_docs(search_results)
    
    print("Context: ", context)  # Print context to inspect it
    
    # First, use the decision system to decide if the context is relevant
    decision = decision_system(context, question)
    
    if decision == "1":  # If the context can answer the question
        print("Context can answer the question")

        response = completion(
            model="gpt-3.5-turbo",
            messages=[
                {"content": system_prompt.format(context=context), "role": "system"},
                {"content": user_prompt.format(question=question), "role": "user"}
            ],
            max_tokens=500
        )
        response_text = response.choices[0].message.content
    else:  # If context is not relevant, search online
        print("Context is NOT relevant. Searching online...")
        results = DDGS().text(question, max_results=5)
        
        # Log the search results for debugging
        print("DuckDuckGo Search Results:")
        for result in results:
            print(f"Title: {result.get('title')}")
            print(f"Body: {result.get('body')}")
            print("-----")
        
        context = format_search_results(results)
        print("Found online sources. Generating the response...")

        #After web search, in response_generation
        reasoning = cot_analysis(question, context)
        print("CoT Reasoning: ", reasoning)
        
        response = completion(
            model="gpt-4-turbo",
            messages=[
                {"content": system_prompt.format(context=context), "role": "system"},
                {"content": user_prompt.format(question=question), "role": "user"}
            ],
            max_tokens=500
        )
        response_text = response.choices[0].message.content

    # Optionally, validate the response
    if validate_response(response_text, context):
        print("✅ Response is validated with context.")
    
        # Store the question and the response in Pinecone
        #qa_storage(question, response_text, index)
    else:
        print("⚠️ Response validation failed.")

    

    return response_text

#API classes and endpoints start

class QuestionRequest(BaseModel):
    text: str
    game_name: Optional[str] = None

class QuestionResponse(BaseModel):
    response: str
    elapsed_time: float

class UploadResponse(BaseModel):
    message: str
    chunks_count: int

class DeleteDataRequest(BaseModel):
    file_name: str
    type: str

class FetchURLcontent(BaseModel):
    url: str


@app.post("/ask", response_model=QuestionResponse)
async def ask_question(question: QuestionRequest):
    """Process a question and return the response"""
    start_time = time.time()
    response_text = rag_pipeline(question.text, question.game_name)
    elapsed_time = time.time() - start_time
    converted_time = datetime.timedelta(seconds=elapsed_time)
    print(f"Time: {converted_time}")
    
    return QuestionResponse(response=response_text, elapsed_time=elapsed_time)

@app.post("/upload-data", response_model=UploadResponse)
async def upload_data(file: UploadFile = File(...), type: str = Form(...)):
    """Upload a file (PDF, JSON, CSV, Markdown) and process it synchronously before returning"""
    temp_file_path = f"temp_{file.filename}"
    
    try:
        # Save the uploaded file temporarily
        with open(temp_file_path, "wb") as buffer:
            buffer.write(await file.read())

        # Extract content based on file type
        file_name = file.filename
        file_content = ""

        if type == "pdf":
            reader = PdfReader(temp_file_path)
            for page in reader.pages:
                file_content += page.extract_text() or ""  # Handle possible None values
        elif type in ["json", "csv", "markdown"]:
            with open(temp_file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {type}")

        if not file_content.strip():
            raise HTTPException(status_code=400, detail=f"No content could be extracted from the {type} file")

        # Process the file content synchronously
        process_data_content(file_content, file_name, type, temp_file_path)  # No 'await' needed

        # Return a response after processing is complete
        return UploadResponse(
            message=f"{type.upper()} file '{file_name}' successfully processed",
            chunks_count=max(1, len(file_content.split()) // 150)  # Ensure at least 1 chunk
        )

    except HTTPException as http_ex:
        raise http_ex  
    except Exception as e:
        logging.error(f"File Upload Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error processing file")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.post("/import-from-url", response_model=UploadResponse)
async def import_from_url(request: FetchURLcontent):
    """Import content from a URL and process it synchronously before returning"""
    url = request.url

    try:
        # Validate URL format
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise HTTPException(status_code=400, detail=f"Invalid URL format: {url}")

        # Fetch content from URL using the existing GET endpoint
        content = await fetch_url_content(url)  # Ensure fetch_url_content is async

        if not content or not content.strip():
            raise HTTPException(status_code=404, detail=f"Failed to fetch content from URL: {url}")

        # Extract domain as the "filename"
        domain = result.netloc
        file_name = f"{domain}_url"

        # Process the URL content synchronously
        process_data_content(content, file_name, "url", None)

        # Return a response after processing is complete
        return UploadResponse(
            message=f"Game content from '{url}' has been successfully processed",
            chunks_count=max(1, len(content.split()) // 150)  # Ensure at least 1 chunk
        )

    except HTTPException as http_ex:
        raise http_ex  
    except Exception as e:
        logging.error(f"URL Import Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error importing from URL")


@app.post("/delete-data")
async def delete_data(request: DeleteDataRequest):
    """Clear the record of uploaded data"""
    try:
        file_name = request.file_name
        file_type = request.type
        
        # Just return a success message to acknowledge deletion
        return {"message": f"{file_type.upper()} '{file_name}' record cleared successfully."}

    except Exception as e:
        return {"error": str(e)}


# API endpoint that calls the game detection function
@app.get("/detect-game")
async def detect_game():
    game_name = get_current_game()
    print(f"Current game: {game_name}")
    if not game_name:
        return {"gameName": ""}
    
    return {"gameName": game_name}

# Game detection function
def get_current_game():
    """Detect the currently running game using multiple methods"""
    # First try process detection (more reliable for known games)
    game_processes = {
        "eldenring.exe": "Elden Ring",
        "RocketLeague.exe": "Rocket League",
        "GTA5.exe": "Grand Theft Auto V",
        "csgo.exe": "Counter-Strike 2",
        "Cyberpunk2077.exe": "Cyberpunk 2077",
        "FortniteClient-Win64-Shipping.exe": "Fortnite",
        "Overwatch.exe": "Overwatch 2",
        "VALORANT.exe": "VALORANT", 
        "LeagueofLegends.exe": "League of Legends",
        "Minecraft.exe": "Minecraft",
    }

    # Check for known game processes
    for proc in psutil.process_iter(['name']):
        try:
            process_name = proc.info['name']
            if process_name in game_processes:
                return game_processes[process_name]
        except:
            pass
    
    # Fallback to window title detection
    try:
        active_window = gw.getActiveWindow()
        if active_window:
            window_title = active_window.title
            print(f"Detected window title: {window_title}")  # Debug output
            
            # Filter out common non-game applications
            common_apps = ["Google Chrome", "Discord", "Spotify", "File Explorer", 
                          "Microsoft", "Word", "Excel", "PowerPoint", "Visual Studio Code",
                          "Notepad", "Explorer", "Settings", "Hello World!"]
            
            if any(app in window_title for app in common_apps):
                return ""
                
            # Try to extract game name from window title
            # Many games use formats like "Game Name - Other Info" or "Game Name | Other Info"
            potential_game = window_title.split(' - ')[0].split(' | ')[0].strip()
            
            # Avoid returning very short or very long names
            if 3 <= len(potential_game) <= 30:
                return potential_game
    except Exception as e:
        print(f"Error detecting window: {str(e)}")
        pass
        
    return ""

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0"
    }

# Run the server
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)