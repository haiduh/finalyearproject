from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec
from litellm import completion
from dotenv import load_dotenv
from duckduckgo_search import DDGS
import requests
import json
import time
import os
import re
import uuid
import hashlib


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

# Optional PDF Path (Set to None or leave empty if not provided)
pdf_path = r"F:\GitHub\finalyearproject\RAG\mock_data.pdf"  # or set it as an empty string "" or leave it as None
pdf_name = None
pdf_content = None

# Check if PDF path is provided, if not, allow the process to continue
if pdf_path:
    pdf_name = os.path.basename(pdf_path)
    pdf_content = fetch_pdf_content(pdf_path)
    if pdf_content:
        print("✅ PDF content retrieved successfully.")
        print(pdf_content)  # Print or process the PDF content
    else:
        print("❌ No text extracted from the PDF.")
else:
    print("❌ No PDF provided. Skipping PDF extraction.")
    pdf_content = None  # Ensure pdf_content is None if no PDF is provided

# If no PDF content is available, exit or handle as needed.
if not pdf_content:
    print("❌ No PDF content available. Continuing with other sources...")

# Proceed with the rest of your logic even if PDF content is missing
# Split and clean text from PDF if available, or continue with other sources
token_size = 150
text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    model_name="gpt-4",
    chunk_size=token_size,
    chunk_overlap=0,
)

def clean_text(text: str) -> str:
    """Removes extra spaces and newlines."""
    text = text.replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', text).strip()

text_chunks = []
if pdf_content:  # Only split the text if PDF content is available
    text_chunks = [clean_text(chunk) for chunk in text_splitter.split_text(pdf_content)]
    print(f"✅ Total Chunks from PDF: {len(text_chunks)}")
else:
    print("❌ Skipping text splitting since no PDF content was found.")

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

# Check if text chunks were extracted from the PDF and proceed
embeddings_objects = []
if text_chunks:  # Only generate embeddings if there are text chunks
    embeddings_objects = get_embeddings(text_chunks)
    if embeddings_objects is None:
        print("❌ Failed to generate embeddings.")
        exit(1)
else:
    print("❌ No text chunks available for embeddings.")

# Pinecone API Setup
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    print("❌ ERROR: Missing PINECONE_API_KEY.")
    exit(1)

pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "example-index"

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

# Upsert data into Pinecone (only if embeddings were generated)
if embeddings_objects:
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


# Search function
def search(query_text: str, top_k: int = 3):
    """Search Pinecone index for relevant content."""
    query_embedding = get_embeddings([query_text])[0]["embedding"]
    results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True, namespace="game_docs")
    return results

# Format retrieved docs for LLM
def format_docs(search_results):
    """Format Pinecone search results into readable context."""
    if not search_results["matches"]:
        return ""
    
    return "\n\n".join([match["metadata"]["source_text"] for match in search_results["matches"]])

# Decision system prompt
decision_system_prompt = """
Your task is to determine if the given context provides an answer to the following question.
- If the context contains enough information to answer the question, return `1`.
- If the context does not contain enough information to answer the question, return `0`.
Do not add any explanations or additional text. Just return `1` or `0`.

Context: {context}
"""

# LLM response prompt
system_prompt = """
You are an expert gaming assistant. Your job is to answer the player's question using ONLY the provided context.
- If the context does not provide an answer, provide a related but slightly different answer from the context.
- Your answers should be as detailed as possible, however, if not necessary, provide a clear, concise answer. 
If applicable, provide step-by-step instructions or explanations.
Do NOT make stuff up.

Context: {context}
"""

user_prompt = """
Question: {question}

Answer:
"""

# Initialize DuckDuckGo Search
def format_search_results(results):
    return "\n\n".join(doc["body"] for doc in results)

def search(query_text: str, namespaces: list, top_k: int = 3):
    """Search Pinecone index for relevant content in each namespace."""
    query_embedding = get_embeddings([query_text])[0]["embedding"]
    
    # Initialize an empty list to store search results from each namespace
    all_results = []
    
    # Loop through each namespace and perform the query
    for namespace in namespaces:
        results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True, namespace=namespace)
        all_results.extend(results["matches"])  # Add the results from each namespace
    
    return {"matches": all_results}  # Return combined results from all namespaces

def format_docs(search_results):
    """Format Pinecone search results into readable context."""
    if not search_results["matches"]:
        return ""
    
    return "\n\n".join([match["metadata"]["source_text"] for match in search_results["matches"]])

# Decision system to decide if context can answer the question
def decision_system(context, question):
    """Decision system to decide if context can answer the question."""
    # Format the prompt with the context and question
    decision_prompt = decision_system_prompt.format(context=context)
    
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

# Modify the response_generation function to include namespaces when calling search
def response_generation(question):
    # Define the namespaces
    namespaces = ["game_docs", "game_queries"]
    
    # Search context in Pinecone
    search_results = search(question, namespaces)
    context = format_docs(search_results)
    
    print("Context: ", context)  # Print context to inspect it
    
    # First, use the decision system to decide if the context is relevant
    decision = decision_system(context, question)
    
    if decision == "1":  # If the context can answer the question
        print("Context can answer the question")
        response = completion(
            model="gpt-4o-mini",
            messages=[{"content": system_prompt.format(context=context), "role": "system"}, {"content": user_prompt.format(question=question), "role": "user"}],
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
        response = completion(
            model="gpt-4o-mini",
            messages=[{"content": system_prompt.format(context=context), "role": "system"}, {"content": user_prompt.format(question=question), "role": "user"}],
            max_tokens=500
        )
        response_text = response.choices[0].message.content

    # Store the question and the response in Pinecone
    qa_storage(question, response_text, index)

    return response_text


# Example usage:
question = input("Enter a Question: ")
response = response_generation(question)
print("🤖 AI Response:", response)
