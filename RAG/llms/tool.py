from pypdf import PdfReader
from contextlib import asynccontextmanager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec
from litellm import completion
from dotenv import load_dotenv
from duckduckgo_search import DDGS  # Keep web search capability
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


def clean_text(text: str) -> str:
    """Removes extra spaces and newlines."""
    text = text.replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', text).strip()


# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("❌ ERROR: Missing OPENAI_API_KEY.")
    exit(1)

# Generate embeddings
def get_embeddings(texts, model="text-embedding-3-small", api_key=OPENAI_API_KEY):
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
You are an AI assistant embedded in an in-game overlay. Your goal is to provide concise, game-specific assistance in a structured format.

Keep responses brief and to the point (2-3 sentences).
Prioritize clear, actionable information (e.g., item locations, enemy weaknesses).
Avoid unnecessary explanations—only provide what the player needs.
If the game is unknown, give general gaming tips instead.
Format responses clearly for easy readability in an overlay UI.
Example formats:
[Tip] "Use fire attacks to weaken this enemy."
[Location] "The Dectus Medallion (Left) is in Fort Haight, southeast of Mistwood."
[General] "If you're lost, check for landmarks or quest markers on the map."

If a query is unclear, ask for clarification in one short sentence.

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

        # Optionally, run Chain-of-Thought analysis before generating response
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
    else:
        print("⚠️ Response validation failed.")

    # Store the question and the response in Pinecone
    # qa_storage(question, response_text, index)

    return response_text


class QuestionRequest(BaseModel):
    text: str
    game_name: Optional[str] = None

class QuestionResponse(BaseModel):
    response: str
    elapsed_time: float

class PdfUploadResponse(BaseModel):
    message: str
    chunks_count: int


@app.post("/ask", response_model=QuestionResponse)
async def ask_question(question: QuestionRequest):
    """Process a question and return the response"""
    start_time = time.time()
    response_text = rag_pipeline(question.text, question.game_name)
    elapsed_time = time.time() - start_time
    
    return QuestionResponse(response=response_text, elapsed_time=elapsed_time)

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
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=150,  # Token size
            chunk_overlap=20,  # Small overlap to maintain context between chunks
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
                    "metadata": {"source_text": text, "pdf_name": pdf_name}
                }
                vectors_to_upsert.append(record)
        
        # Batch upsert to Pinecone (more efficient)
        if vectors_to_upsert:
            index.upsert(vectors=vectors_to_upsert, namespace="game_docs")
            print(f"✅ {len(vectors_to_upsert)} new chunks successfully inserted into Pinecone.")
        else:
            print("⚠️ No new content to insert.")
    
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.get("/detect_game")
async def detect_game():
    """Detect the current running game"""
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

    return ""

# Health check endpoint
@app.get("/health")
async def health_check():
    """Check if the service is running"""
    return {"status": "ok", "pinecone_connected": index is not None}

# Run the server
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)