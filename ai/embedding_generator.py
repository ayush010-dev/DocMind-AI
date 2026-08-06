from sentence_transformers import SentenceTransformer

# Load model only once
model = SentenceTransformer("BAAI/bge-small-en-v1.5")


def generate_embeddings(chunks):

    embeddings = model.encode(chunks)

    return embeddings