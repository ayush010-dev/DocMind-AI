import re
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter

def normalize_text(text: str) -> str:
    """
    Removes all non-alphanumeric characters and converts to lowercase.
    e.g., 'B-3/137' -> 'b3137'
    """
    return re.sub(r'[^a-z0-9]', '', text.lower())

def chunk_text(blocks):
    """
    Takes page blocks and splits them into:
    1. semantic_chunks: 1000-character chunks for Vector DB (Chroma).
    2. exact_records: Logical line/row records for Structured DB (SQLite).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    semantic_chunks = []
    exact_records = []
    
    if isinstance(blocks, str):
        blocks = [{"text": blocks}]

    for block in blocks:
        text = block.get("text", "")
        if not text.strip():
            continue
            
        metadata = {k: v for k, v in block.items() if k != "text"}
        
        # 1. Semantic Chunks
        chunks = splitter.split_text(text)
        for i, chunk in enumerate(chunks):
            semantic_chunks.append({
                "text": chunk,
                "metadata": metadata,
                "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}"
            })

        # 2. Exact Records (Logical row-level splitting)
        # We assume newlines generally demarcate tabular rows or distinct logical lines
        lines = text.split('\n')
        
        # Group lines into small logical blocks (e.g. 2-3 lines) to preserve multi-line records
        # If it's a dense table, 1 line might be 1 record. We'll store sliding windows of 2 lines as records.
        for i in range(len(lines)):
            # We store the exact line and its context
            window = lines[i:i+2]
            record_text = "\n".join(window).strip()
            if not record_text:
                continue
                
            norm_text = normalize_text(record_text)
            if len(norm_text) < 2:
                continue
                
            exact_records.append({
                "record_id": f"rec_{uuid.uuid4().hex[:8]}",
                "text": record_text,
                "normalized_text": norm_text,
                "metadata": metadata
            })

    return {
        "semantic_chunks": semantic_chunks,
        "exact_records": exact_records
    }
