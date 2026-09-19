from sentence_transformers import SentenceTransformer

# Load model only once
model = SentenceTransformer("BAAI/bge-small-en-v1.5")


def generate_embeddings(chunks):

    if chunks and isinstance(chunks[0], dict):
        texts = [chunk.get("text", "") for chunk in chunks]
    else:
        texts = chunks

    embeddings = model.encode(texts)

    return embeddings