import json
import re

def classify_intent_and_resolve_query(question: str, chat_history: list = None, active_documents: list = None) -> dict:
    if chat_history is None: chat_history = []
    if active_documents is None: active_documents = []

    q_raw = question.strip()
    q_lower = q_raw.lower()
    
    target_document_ids = [d["document_id"] for d in active_documents]
    
    # 1. PAGE QUERY
    pm = re.search(r'\b(?:page)\s*(\d+)\b', q_lower)
    if pm or "this page" in q_lower or "first page" in q_lower:
        target_page = int(pm.group(1)) if pm else 1
        return {"intent": "PAGE_QUERY", "search_query": q_raw, "entity_name": None, "target_page": target_page, "target_document_ids": target_document_ids}
        
    # 2. COUNT AGGREGATION
    count_kws = [r"\bhow many\b", r"\btotal\b", r"\bcount\b", r"\bnumber of\b", r"\bsum\b"]
    if any(re.search(k, q_lower) for k in count_kws):
        return {"intent": "COUNT_AGGREGATION", "search_query": q_raw, "entity_name": None, "target_page": None, "target_document_ids": target_document_ids}
        
    # 3. STRUCTURED LOOKUP
    # e.g., "Piyush with address B3/137" or "Piyush father name Ramesh"
    structured_kws = ["with address", "address", "father", "son of", "wife of", "age", "id", "roll number"]
    if any(k in q_lower for k in structured_kws) and len(q_lower.split()) > 3:
        # It's likely a structured lookup combining name and constraints
        return {"intent": "STRUCTURED_LOOKUP", "search_query": q_raw, "entity_name": q_raw, "target_page": None, "target_document_ids": target_document_ids}
        
    # 4. SUMMARY
    summary_kws = ["summar", "about", "explain", "overview", "what is in"]
    if any(k in q_lower for k in summary_kws) and not any(k in q_lower for k in ["how to", "why did"]):
        return {"intent": "SUMMARY", "search_query": q_raw, "entity_name": None, "target_page": None, "target_document_ids": target_document_ids}
        
    # 5. EXACT LOOKUP
    # e.g., "Is there anyone named Piyush", "Piyush", "serial number 698"
    exact_kws = ["named", "serial number", "id", "find"]
    if any(k in q_lower for k in exact_kws) or (len(q_lower.split()) <= 3 and not any(k in q_lower for k in ["what", "how", "why", "explain"])):
        # Treat short queries or specific entity requests as exact lookups
        entity = re.sub(r'^(is there anyone named|find|who is|what is the serial number of)\s+', '', q_lower).strip()
        return {"intent": "EXACT_LOOKUP", "search_query": q_raw, "entity_name": entity or q_raw, "target_page": None, "target_document_ids": target_document_ids}
        
    # 6. Default to SEMANTIC QA
    return {"intent": "SEMANTIC_QA", "search_query": q_raw, "entity_name": None, "target_page": None, "target_document_ids": target_document_ids}
