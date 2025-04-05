from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model1 = SentenceTransformer('all-MiniLM-L6-v2')  # Open-source embedding model
model2 = SentenceTransformer('multi-qa-MiniLM-L6-dot-v1')  # Another variant

query = "Where can I find spruce logs in Minecraft?"
vector1 = model1.encode([query])
vector2 = model2.encode([query])

print("Similarity:", cosine_similarity(vector1, vector2)[0][0])
