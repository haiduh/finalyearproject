import requests
import json
import time
import os
import re
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec
from litellm import completion
from dotenv import load_dotenv
from duckduckgo_search import DDGS

load_dotenv()

# Fetch content from a URL using Jina AI Proxy
def fetch_url_content(url: str):
    """Fetch content from the given URL."""
    full_url = "https://r.jina.ai/" + url
    try:
        response = requests.get(full_url)
        if response.status_code == 200:
            return response.content.decode('utf-8')
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"❌ Request Failed: {e}")
        return None

# URL to scrape
url = "https://eldenring.wiki.fextralife.com/Black+Knight"
content = fetch_url_content(url)

if not content:
    print("❌ Failed to retrieve content.")
    exit(1)

print("✅ Content retrieved successfully.")

# Split and clean text
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

text_chunks = [clean_text(chunk) for chunk in text_splitter.split_text(content)]
print(f"✅ Total Chunks: {len(text_chunks)}")

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

embeddings_objects = get_embeddings(text_chunks)
if embeddings_objects is None:
    print("❌ Failed to generate embeddings.")
    exit(1)

embeddings = [obj["embedding"] for obj in embeddings_objects]
print(f"✅ Embedding Length: {len(embeddings[0])}")

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

# Upsert data into Pinecone
records = [
    {"id": str(uuid.uuid4()), "values": embedding, "metadata": {"source_text": text, "url": url}}
    for text, embedding in zip(text_chunks, embeddings)
]

index.upsert(vectors=records, namespace="eldenring")
print("✅ Data successfully inserted into Pinecone.")

# Search function
def search(query_text: str, top_k: int = 3):
    """Search Pinecone index for relevant content."""
    query_embedding = get_embeddings([query_text])[0]["embedding"]
    results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True, namespace="eldenring")
    return results

# Format retrieved docs for LLM
def format_docs(search_results):
    """Format Pinecone search results into readable context."""
    if not search_results["matches"]:
        return ""
    
    return "\n\n".join([match["metadata"]["source_text"] for match in search_results["matches"]])

# Decision system prompt
decision_system_prompt = """
Your job is to decide if a given question can be answered with a given context.
If context can answer the question, return 1.
If not, return 0.

Do not return anything except for 0 or 1.

Context: {context}
"""

# LLM response prompt
system_prompt = """
You are an expert gaming assistant.
Answer the player's question using ONLY the given context.
If the context does not contain the answer, say "I don't know. Here is a similar answer.", and provide a similar answer.
Your response must be DETAILED, and if applicable, provide STEP-BY-STEP tutorials.

Context: {context}
"""

user_prompt ="""
Question: {question}

Answer:
"""

# Initialize DuckDuckGo Search
def format_search_results(results):
    return "\n\n".join(doc["body"] for doc in results)

def search(query_text: str, top_k: int = 3):
    """Search Pinecone index for relevant content."""
    query_embedding = get_embeddings([query_text])[0]["embedding"]
    results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True, namespace="eldenring")
    return results

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

# Modified answer function
def answer_with_context_or_ddgs(question):
    # Search context in Pinecone
    search_results = search(question)
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
        return response.choices[0].message.content
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
        return response.choices[0].message.content


# Example usage:
question = input("Enter a Question: ")
response = answer_with_context_or_ddgs(question)
print("🤖 AI Response:", response)


