import uuid
import chromadb

client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(
    name="documents"
)


def store_embeddings(chunks, embeddings, file_name, document_id):

    ids = [str(uuid.uuid4()) for _ in chunks]

    metadata = [
    {
        "document_id": document_id,
        "source": file_name,
        "chunk": i
    }
    for i in range(len(chunks))
]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist(),
        metadatas=metadata
    )


def search_documents(query_embedding, document_id):

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=3,
        where={
            "document_id": document_id
        }
    )

    return results