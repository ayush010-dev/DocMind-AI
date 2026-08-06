from ai.embedding_generator import generate_embeddings
from ai.vector_store import search_documents
from ai.gemini_chat import generate_answer
from ai.prompts import SYSTEM_PROMPT


def ask_document(question, document_id):

    # Step 1
    query_embedding = generate_embeddings([question])[0]

    # Step 2
    results = search_documents(
    query_embedding,
    document_id
)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    # Step 3
    context = "\n\n".join(results["documents"][0])

    # Step 4
    prompt = f"""
{SYSTEM_PROMPT}

Context:
{context}

Question:
{question}

Answer:
"""

    # Step 5
    answer = generate_answer(prompt)

    return {
    "answer": answer,
    "source": metadatas[0]["source"],
    "chunk": metadatas[0]["chunk"]
}