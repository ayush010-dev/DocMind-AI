import uuid
import chromadb


# ==============================
# ChromaDB Client
# ==============================

client = chromadb.PersistentClient(
    path="chroma_db"
)


# ==============================
# Collection
# ==============================

collection = client.get_or_create_collection(
    name="documents"
)


# ==============================
# Store Embeddings
# ==============================

def store_embeddings(
    chunks,
    embeddings,
    file_name,
    document_id
):
    ids = [
        str(uuid.uuid4())
        for _ in chunks
    ]

    documents = [chunk["text"] for chunk in chunks]

    import datetime
    now_iso = datetime.datetime.utcnow().isoformat()
    
    metadata = []
    for i, chunk in enumerate(chunks):
        meta = {
            "document_id": document_id,
            "source": file_name,
            "filename": file_name,
            "uploaded_at": now_iso,
            "chunk": i
        }
        meta.update(chunk.get("metadata", {}))
        metadata.append(meta)

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings.tolist(),
        metadatas=metadata
    )


# ==============================
# Search Documents (with scores)
# ==============================

def search_documents(
    query_embedding,
    document_ids: list[str],
    n_results=12
):
    """
    Query ChromaDB and always return L2 distances.
    n_results is set to 12 by default so the pipeline
    can re-rank and trim to the best chunks.
    """
    try:
        results = collection.query(
            query_embeddings=[
                query_embedding.tolist()
            ],
            n_results=n_results,
            where={
                "document_id": {"$in": document_ids}
            },
            include=["documents", "metadatas", "distances"]
        )
        return results
    except Exception as e:
        print(f"[VectorStore Error] search_documents failed: {e}")
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


def normalize_l2_to_relevance(distance: float) -> float:
    """
    Convert a ChromaDB L2 distance to a 0-1 relevance score.
    Lower L2 distance = higher relevance.
    Score of 1.0 means identical; 0.0 means completely unrelated.
    Using an exponential decay that maps:
      distance=0.0  -> score=1.0
      distance=1.0  -> score~0.37
      distance=1.5  -> score~0.22
      distance=2.0  -> score~0.14
    """
    import math
    return math.exp(-distance)


def get_chunks_by_metadata(document_ids: list[str], page=None, slide=None):
    """
    Directly retrieves document chunks matching page or slide filters.
    Returns empty lists instead of a wrong-page fallback when no match found.
    """
    filters_to_try = []
    if page is not None:
        filters_to_try.append({"$and": [{"document_id": {"$in": document_ids}}, {"page": page}]})
        # Try slide fallback (some PDFs stored as slides)
        filters_to_try.append({"$and": [{"document_id": {"$in": document_ids}}, {"slide": page}]})
    elif slide is not None:
        filters_to_try.append({"$and": [{"document_id": {"$in": document_ids}}, {"slide": slide}]})
        filters_to_try.append({"$and": [{"document_id": {"$in": document_ids}}, {"page": slide}]})

    if not filters_to_try:
        filters_to_try.append({"document_id": {"$in": document_ids}})

    for wf in filters_to_try:
        try:
            results = collection.get(
                where=wf,
                include=["documents", "metadatas"]
            )
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            if docs:
                return {
                    "documents": [docs],
                    "metadatas": [metas],
                    "distances": [[0.0] * len(docs)]
                }
        except Exception as e:
            print(f"[VectorStore Warning] get_chunks_by_metadata failed on filter {wf}: {e}")

    # No matching page/slide found — return empty (do NOT fall back to chunk 0)
    return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


def get_all_document_chunks(document_ids: list[str], limit=15):
    """
    Retrieves document chunks for general summary/overview queries.
    """
    try:
        results = collection.get(
            where={"document_id": {"$in": document_ids}},
            limit=limit,
            include=["documents", "metadatas"]
        )
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        return {
            "documents": [docs],
            "metadatas": [metas],
            "distances": [[0.0] * len(docs)]
        }
    except Exception as e:
        print(f"[VectorStore Warning] get_all_document_chunks failed: {e}")
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

def get_all_document_chunks_unlimited(document_ids: list[str]):
    """
    Retrieves ALL document chunks without limit for full-text lookup.
    """
    try:
        results = collection.get(
            where={"document_id": {"$in": document_ids}},
            include=["documents", "metadatas"]
        )
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        return {
            "documents": [docs],
            "metadatas": [metas],
            "distances": [[0.0] * len(docs)]
        }
    except Exception as e:
        print(f"[VectorStore Warning] get_all_document_chunks_unlimited failed: {e}")
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

# ==============================
# Exact Match Search
# ==============================

def search_documents_exact(keyword: str, document_ids: list[str], limit=15):
    """
    Query ChromaDB for exact keyword matches.
    Checks multiple cases to approximate case-insensitivity.
    """
    if len(keyword) < 3: return {"documents": [[]], "metadatas": [[]]}

    kw_lower = keyword.lower()
    kw_upper = keyword.upper()
    kw_title = keyword.title()
    kw_exact = keyword

    variations = list(set([kw_lower, kw_upper, kw_title, kw_exact]))
    or_clauses = [{"$contains": var} for var in variations]

    try:
        results = collection.get(
            where={"document_id": {"$in": document_ids}},
            where_document={"$or": or_clauses},
            limit=limit,
            include=["documents", "metadatas"]
        )
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        return {
            "documents": [docs],
            "metadatas": [metas]
        }
    except Exception as e:
        print(f"[VectorStore Error] search_documents_exact failed: {e}")
        return {"documents": [[]], "metadatas": [[]]}