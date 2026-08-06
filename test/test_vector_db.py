from ai.embedding_generator import generate_embeddings
from ai.vector_store import store_embeddings

chunks = [
    "Artificial Intelligence",
    "Machine Learning",
    "Deep Learning"
]

embeddings = generate_embeddings(chunks)

store_embeddings(chunks, embeddings)

print("✅ Embeddings Stored Successfully!")