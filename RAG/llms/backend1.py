from pypdf import PdfReader
from contextlib import asynccontextmanager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec
from litellm import completion
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
import psutil
import requests
import json
import time
import os
import re
import uuid
import hashlib
import uvicorn

# Create FastAPI app
app = FastAPI(
    title="RAG API",
    description="RAG System API for Q&A",
    lifespan=lambda app: lifespan(app)  # Add lambda here to use the lifespan context manager
)

# Add CORS middleware to allow cross-origin requests (needed for Tauri)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Load environment variables
load_dotenv()

# Function to fetch content from a PDF file
def fetch_pdf_content(pdf: str):
    """Fetch content from a PDF file."""
    reader = PdfReader(pdf)  # Use the variable 'pdf' for the file path
    number_of_pages = len(reader.pages)
    content = ""
    
    # Loop through each page and extract text
    for page_num in range(number_of_pages):
        page = reader.pages[page_num]
        content += page.extract_text()
    
    return content

# Initialize global variables for Pinecone
pc = None
index = None
index_name = "example-index"

# Initialize Pinecone on startup
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

    # Shutdown logic (if necessary)
    print("🔌 Shutting down Pinecone client.")

# Helper functions (keeping original code)
def clean_text(text: str) -> str:
    """Removes extra spaces and newlines."""
    text = text.replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', text).strip()

# Generate embeddings
def get_embeddings(texts, model="text-embedding-3-small", api_key=None):
    """Fetch OpenAI embeddings."""
    # Use environment variable if API key not provided
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: Missing OPENAI_API_KEY.")
        return None
        
    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"input": texts, "model": model}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        return response.json()["data"]
    else:
        print(f"❌ Embedding Error {response.status_code}: {response.text}")
        return None

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

# Search function
def search(query_text: str, namespaces=["game_docs", "game_queries"], top_k: int = 3):
    """Search Pinecone index for relevant content."""
    query_embedding = get_embeddings([query_text])[0]["embedding"]
    
    all_results = []
    for namespace in namespaces:
        results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True, namespace=namespace)
        all_results.extend(results["matches"])
    return {"matches": all_results}

# Format retrieved docs for LLM
def format_docs(search_results):
    """Format Pinecone search results into readable context with error handling."""
    if not search_results["matches"]:
        return ""
    
    formatted_results = []
    for match in search_results["matches"]:
        # Check if metadata exists and has the required field
        if "metadata" in match:
            metadata = match["metadata"]
            if "source_text" in metadata:
                formatted_results.append(metadata["source_text"])
            elif "question" in metadata and "response" in metadata:
                # Handle QA pairs from the queries namespace
                formatted_results.append(f"Q: {metadata['question']}\nA: {metadata['response']}")
            elif "question" in metadata:
                formatted_results.append(f"Related question: {metadata['question']}")
            elif "response" in metadata:
                formatted_results.append(f"Related answer: {metadata['response']}")
    
    return "\n\n".join(formatted_results)

# Decision system prompt
decision_system_prompt = """
Your task is to evaluate if the context fully answers the question. Consider:
1. Are all key elements of the question addressed?
2. Is the context specific to the game being asked about?
3. Are there any contradictions between context and question?

Return `1` if the context fully answers the question, `0` if it doesn't.
Do NOT add explanations. Just return `1` or `0`.

Context: {context}
Question: {question}
"""

# LLM response prompt
system_prompt = """
You are an expert gaming assistant. Follow these rules:
1. Use ONLY the provided context to answer.
2. If the context doesn't fully answer the question, provide a related answer and clarify it's not exact.
3. Structure responses with:
   - 📌 Key Details
   - 🛠️ Required Items/Mechanics
   - 🗺️ Step-by-Step Instructions (if applicable)
   - 💡 Pro Tips (if applicable)
4. Never invent information. If unsure, provide a similar answer.
5. If it is not related to a game, do not provide answer.

Context: {context}
"""
user_prompt = """
Question: {question}

Additional Instructions:
1. Focus on the most relevant parts of the context.
2. If the question is unclear, ask for clarification.
3. Use game-specific terminology where applicable.

Answer:
"""

# Initialize DuckDuckGo Search
def format_search_results(results):
    return "\n\n".join(doc["body"] for doc in results)

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

# Decision system to decide if context can answer the question
def decision_system(context, question):
    """Decision system to decide if context can answer the question."""
    if not context:
        print("❌ No valid context found. Returning 0.")
        return "0"  # If no context, return "0"
    
    # Format the prompt with the context and question
    decision_prompt = decision_system_prompt.format(context=context, question=question)
    
    # Query the LLM with decision prompt
    decision_response = completion(
        model="gpt-4o-mini",
        messages=[{"content": decision_prompt, "role": "system"}],
        max_tokens=3
    )
    
    # Return 1 or 0 based on LLM's decision
    decision = decision_response.choices[0].message.content.strip()
    return decision

# Function to store question and response in Pinecone
def qa_storage(question: str, response: str, index, namespace="game_queries"):
    """Store the question and response pair in Pinecone index."""
    # Generate embeddings for the question and response
    question_embedding = get_embeddings([question])[0]["embedding"]
    response_embedding = get_embeddings([response])[0]["embedding"]
    
    # Create a unique ID for this entry
    unique_id = str(uuid.uuid4())
    
    # Create records for the question and response
    # Include source_text field for compatibility with format_docs
    records = [
        {
            "id": f"{unique_id}_question", 
            "values": question_embedding, 
            "metadata": {
                "question": question, 
                "type": "question",
                "source_text": f"Question: {question}"  # Add source_text for compatibility
            }
        },
        {
            "id": f"{unique_id}_response", 
            "values": response_embedding, 
            "metadata": {
                "response": response, 
                "type": "response",
                "source_text": f"Response: {response}"  # Add source_text for compatibility
            }
        }
    ]
    
    # Upsert the records into Pinecone
    index.upsert(vectors=records, namespace=namespace)
    print("✅ Question and Response successfully stored in Pinecone.")

# AGENTIC FUNCTIONS (keeping original code)
def determine_search_strategy(question: str) -> str:
    """Analyze question to determine optimal search strategy."""
    prompt = f"""
    Analyze this gaming question and determine the best search strategy.
    Return only one of these options:
    - local_first: If the question seems specific to documented game mechanics
    - web_first: If the question likely needs up-to-date information
    - hybrid: If both local context and web information are needed
    
    Question: {question}
    """
    
    response = completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=10
    )
    
    strategy = response.choices[0].message.content.strip().lower()
    # Default to hybrid if response isn't one of the expected values
    if strategy not in ["local_first", "web_first", "hybrid"]:
        return "hybrid"
    return strategy

def needs_more_information(question: str, context: str, reasoning: str) -> bool:
    """Determine if more information is needed based on current context."""
    prompt = f"""
    Based on the following:
    Question: {question}
    Current Context: {context}
    Current Reasoning: {reasoning}
    
    Is more information needed to provide a complete answer? 
    Return only 1 (more info needed) or 0 (sufficient info).
    """
    
    response = completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=3
    )
    
    return response.choices[0].message.content.strip() == "1"

def generate_sub_queries(question: str, reasoning: str) -> list:
    """Generate specific sub-queries to fill knowledge gaps."""
    prompt = f"""
    Based on this question and reasoning, generate 2-3 specific sub-queries
    to fill knowledge gaps. Format as a list, each on a new line.
    
    Question: {question}
    Reasoning: {reasoning}
    """
    
    response = completion(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    return [line.strip() for line in response.choices[0].message.content.split("\n") if line.strip()]

def gather_additional_context(sub_queries: list) -> str:
    """Gather additional context using sub-queries."""
    additional_contexts = []
    
    for query in sub_queries:
        # Try local search first
        search_results = search(query, namespaces=["game_docs", "game_queries"], top_k=2)
        local_context = format_docs(search_results)
        
        # If local search doesn't yield much, try web search
        if not local_context or len(local_context) < 100:
            results = DDGS().text(query, max_results=5)
            web_context = format_search_results(results)
            additional_contexts.append(web_context)
        else:
            additional_contexts.append(local_context)
    
    return "\n\n".join(additional_contexts)

def evaluate_response_quality(response: str, context: str, question: str) -> int:
    """Evaluate the quality of response on a scale of 1-10."""
    prompt = f"""
    Evaluate this response on a scale of 1-10 based on:
    - Relevance to the question
    - Use of context
    - Completeness
    - Gaming expertise demonstrated
    
    Question: {question}
    Context: {context}
    Response: {response}
    
    Return only a single number from 1-10.
    """
    
    response = completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=3
    )
    
    try:
        score = int(response.choices[0].message.content.strip())
        return min(max(score, 1), 10)  # Ensure score is between 1-10
    except ValueError:
        return 7  # Default score if parsing fails

def refine_response(response: str, context: str, question: str, reasoning: str) -> str:
    """Refine the response to improve quality."""
    prompt = f"""
    Refine this gaming response to improve quality. Add relevant details from the context,
    improve structure, and ensure it addresses all aspects of the question.
    
    Original Question: {question}
    Context: {context}
    Reasoning: {reasoning}
    Current Response: {response}
    
    Improved Response:
    """
    
    refined = completion(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=600
    )
    
    return refined.choices[0].message.content

def agent_controller(question: str):
    """Main agent controller that orchestrates the RAG pipeline."""
    print(f"🤖 Agent received question: {question}")
    
    # Step 1: Analyze question to determine search strategy
    search_strategy = determine_search_strategy(question)
    print(f"🔍 Selected search strategy: {search_strategy}")
    
    # Step 2: Execute search based on strategy
    if search_strategy == "local_first":
        # Try local search first, then fallback to web
        search_results = search(question, namespaces=["game_docs", "game_queries"], top_k=5)
        context = format_docs(search_results)
        decision = decision_system(context, question)
        
        if decision == "0":  # If local search is insufficient
            print("⚠️ Local context insufficient. Switching to web search...")
            results = DDGS().text(question, max_results=5)
            context = format_search_results(results)
    
    elif search_strategy == "web_first":
        # Try web search first
        results = DDGS().text(question, max_results=5)
        context = format_search_results(results)
        
        # If web search doesn't yield good results, try local
        if not context.strip():
            print("⚠️ Web search yielded no results. Trying local database...")
            search_results = search(question, namespaces=["game_docs", "game_queries"], top_k=5)
            context = format_docs(search_results)
    
    elif search_strategy == "hybrid":
        # Combine both sources
        web_results = DDGS().text(question, max_results=3)
        web_context = format_search_results(web_results)
        
        local_results = search(question, namespaces=["game_docs", "game_queries"], top_k=3)
        local_context = format_docs(local_results)
        
        context = local_context + "\n\n" + web_context
    
    # Step 3: Advanced reasoning on the context
    reasoning = cot_analysis(question, context)
    print("💭 Agent reasoning process:")
    print(reasoning)
    
    # Step 4: Determine if further research is needed
    if needs_more_information(question, context, reasoning):
        print("🔄 Agent determined more information is needed...")
        # Try another search strategy or use specific sub-queries
        sub_queries = generate_sub_queries(question, reasoning)
        additional_context = gather_additional_context(sub_queries)
        context += "\n\n" + additional_context
    
    # Step 5: Generate response with enhanced context
    response = completion(
        model="gpt-4-turbo",
        messages=[
            {"content": system_prompt.format(context=context), "role": "system"},
            {"content": user_prompt.format(question=question), "role": "user"}
        ],
        max_tokens=500
    )
    response_text = response.choices[0].message.content
    
    # Step 6: Self-evaluation and refinement
    confidence_score = evaluate_response_quality(response_text, context, question)
    print(f"⭐ Response confidence score: {confidence_score}/10")
    
    if confidence_score < 7:
        print("🔄 Refining response to improve quality...")
        response_text = refine_response(response_text, context, question, reasoning)
    
    # Step 7: Store interaction for learning
    qa_storage(question, response_text, index)
    
    return response_text

# Define API models
class QuestionRequest(BaseModel):
    text: str

class QuestionResponse(BaseModel):
    response: str
    confidence_score: Optional[int] = None

class PdfUploadResponse(BaseModel):
    message: str
    chunks_count: int

# API Endpoints
@app.post("/ask", response_model=QuestionResponse)
async def ask_question(question: QuestionRequest):
    """Process a question and return the response"""
    response_text = agent_controller(question.text)
    return QuestionResponse(response=response_text)

@app.post("/upload-pdf", response_model=PdfUploadResponse)
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a PDF file and process it in the background"""
    # Save the uploaded file temporarily
    temp_file_path = f"temp_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Extract content from PDF
    pdf_name = file.filename
    pdf_content = fetch_pdf_content(temp_file_path)
    
    if not pdf_content:
        os.remove(temp_file_path)  # Clean up
        return PdfUploadResponse(message="No text could be extracted from the PDF", chunks_count=0)
    
    # Process the PDF content in the background
    background_tasks.add_task(process_pdf_content, pdf_content, pdf_name, temp_file_path)
    
    # Return a response immediately
    return PdfUploadResponse(
        message=f"PDF '{pdf_name}' uploaded and processing in background", 
        chunks_count=len(pdf_content.split()) // 150  # Rough estimate of chunks
    )

# Background task to process PDF content
def process_pdf_content(pdf_content, pdf_name, temp_file_path):
    """Process PDF content in the background"""
    try:
        # Split text
        token_size = 150
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=token_size,
            chunk_overlap=0,
        )
        
        # Clean and split text
        text_chunks = [clean_text(chunk) for chunk in text_splitter.split_text(pdf_content)]
        print(f"✅ Total Chunks from PDF: {len(text_chunks)}")
        
        # Generate embeddings
        embeddings_objects = get_embeddings(text_chunks)
        if embeddings_objects is None:
            print("❌ Failed to generate embeddings.")
            return
        
        # Upsert into Pinecone
        for text, embedding in zip(text_chunks, embeddings_objects):
            # Generate a hash for the content to be used as the vector ID
            content_hash = generate_content_hash(text)
            
            # Check if this hash already exists in the Pinecone index
            if not check_if_exists(index, content_hash):
                # Prepare the record to upsert
                record = {
                    "id": content_hash,  # Use content hash as the unique ID
                    "values": embedding["embedding"],
                    "metadata": {"source_text": text, "pdf_name": pdf_name}
                }
                index.upsert(vectors=[record], namespace="game_docs")
                print(f"✅ Data for content hash {content_hash} successfully inserted into Pinecone.")
            else:
                print(f"⚠️ Vector with content hash {content_hash} already exists in Pinecone, skipping upsert.")
    
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.get("/detect_game")
async def detect_game():
    """This is for detecting the game and converting it into a string for React App"""
    game = detecting_game()
    return {"gameName": game}


def detecting_game():
    """A function to detect the game that is currently on"""
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

    for proc in psutil.process_iter(['name']):
        try:
            process_name = proc.info['name']
            if process_name in game_processes:
                return game_processes[process_name]
        except:
            pass

    #If no games are found        
    return ""


# Health check endpoint
@app.get("/health")
async def health_check():
    """Check if the service is running"""
    return {"status": "ok", "pinecone_connected": index is not None}

# Run the server
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)