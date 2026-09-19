import re
from ai.embedding_generator import generate_embeddings
from ai.vector_store import search_documents, search_documents_exact, get_chunks_by_metadata, get_all_document_chunks, normalize_l2_to_relevance
from ai.openai_chat import generate_answer
from ai.prompts import SYSTEM_PROMPT
from ai.intent_classifier import classify_intent_and_resolve_query
from ai.web_search import search_web, filter_web_results

def extract_search_keywords(query: str) -> list[str]:
    words = query.replace("?", "").replace("!", "").replace(",", "").split()
    stop_words = {"what", "who", "where", "when", "why", "how", "is", "are", "the", "a", "an", "of", "in", "for", "to", "and", "or", "on", "document", "find", "show", "me", "details", "about", "uploaded", "this", "file", "pdf", "does", "say", "can", "you", "tell", "from"}
    keywords = [w for w in words if w.lower() not in stop_words and len(w) >= 1]
    return keywords

MIN_DOC_RELEVANCE = 0.10
MIN_WEB_RELEVANCE = 0.15
STRONG_DOC_THRESHOLD = 0.85

def format_document_source(meta):
    doc_id = meta.get("document_id")
    fn = meta.get("filename") or meta.get("source") or "Document"
    page = meta.get("page")
    slide = meta.get("slide")
    sheet = meta.get("sheet")
    section = meta.get("section")
    chunk = meta.get("chunk")

    details = []
    url_fragment = ""
    loc_type = "document"
    loc_val = None

    if page is not None:
        details.append(f"Page {page}")
        url_fragment = f"#page={page}"
        loc_type = "page"
        loc_val = page
    elif slide is not None:
        details.append(f"Slide {slide}")
        url_fragment = f"#slide={slide}"
        loc_type = "slide"
        loc_val = slide
    elif sheet is not None:
        details.append(f"Sheet \"{sheet}\"")
        loc_type = "sheet"
        loc_val = sheet
    elif section is not None:
        details.append(f"Section \"{section}\"")
        loc_type = "section"
        loc_val = section
    elif chunk is not None:
        loc_type = "chunk"
        loc_val = chunk

    label_str = f"{fn}" + (f" · {' · '.join(details)}" if details else "")
    action_url = f"/documents/{doc_id}/source{url_fragment}"

    return {
        "type": "document",
        "document_id": doc_id,
        "filename": fn,
        "source": fn,
        "location_type": loc_type,
        "location": loc_val,
        "page": page,
        "slide": slide,
        "sheet": sheet,
        "section": section,
        "chunk": chunk,
        "label": label_str,
        "url": action_url
    }

def semantic_overlap_check(chunk_text: str, answer_text: str) -> bool:
    def clean_words(text):
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        stop_words = {
            "this", "that", "with", "from", "your", "what", "have", "they", "will", 
            "would", "could", "should", "about", "there", "their", "which", "when", 
            "where", "while", "these", "those", "then", "than", "been", "much", "very",
            "also", "some", "such", "only", "many", "most", "other", "into", "does"
        }
        return set(w for w in words if w not in stop_words)

    chunk_words = clean_words(chunk_text)
    answer_words = clean_words(answer_text)

    if not chunk_words or not answer_words:
        return True

    overlap = len(chunk_words & answer_words)
    required_overlap = 1 if len(answer_words) < 5 else 2
    return overlap >= required_overlap

def ask_document(question, active_documents: list = None, chat_history=None):
    if not active_documents: active_documents = []
    if chat_history is None: chat_history = []
    
    document_ids = [doc["document_id"] for doc in active_documents]

    recent_history = chat_history[-8:]
    history_text = ""
    for message in recent_history:
        role = message.get("role", "").capitalize()
        content = message.get("content", "")
        if role and content: history_text += f"{role}: {content}\n"

    intent_data = classify_intent_and_resolve_query(question, chat_history, active_documents)
    intent = intent_data.get("intent", "DOCUMENT_LOOKUP")
    search_query = intent_data.get("search_query") or question
    entity_name = intent_data.get("entity_name")
    target_page = intent_data.get("target_page")
    target_slide = intent_data.get("target_slide")
    
    if intent_data.get("target_document_ids"):
        document_ids = intent_data["target_document_ids"]

    print(f"[RAG Pipeline] Question: '{question}' | Intent: '{intent}' | Search Query: '{search_query}' | Targets: {document_ids}")

    # Conversational intent is now handled natively by the LLM via prompt.

    candidate_documents = []
    candidate_metadatas = []
    candidate_scores = []
    web_results = []
    doc_context_items = []

    # ============================================
    # 1. Document Chunk Retrieval
    # ============================================
    if intent in ["DOCUMENT_SUMMARY", "SUMMARY"]:
        summary_res = get_all_document_chunks(document_ids, limit=8)
        candidate_documents = summary_res.get("documents", [[]])[0]
        candidate_metadatas = summary_res.get("metadatas", [[]])[0]
        candidate_scores = [1.0] * len(candidate_documents)
    
    elif not candidate_documents and target_page is not None:
        meta_res = get_chunks_by_metadata(document_ids, page=target_page, slide=target_slide)
        p_docs = meta_res.get("documents", [[]])[0]
        p_metas = meta_res.get("metadatas", [[]])[0]
        if p_docs:
            candidate_documents = p_docs
            candidate_metadatas = p_metas
            candidate_scores = [1.0] * len(p_docs)
            
    elif intent in ["DOCUMENT_COMPARISON", "DOCUMENT_CONTRADICTION", "COMPARISON"]:
        query_embedding = generate_embeddings([search_query])[0]
        global_chunk_idx = 1
        for doc_id in document_ids:
            doc_meta = next((d for d in active_documents if d["document_id"] == doc_id), {})
            doc_name = doc_meta.get("filename", "Unknown Document")
            
            doc_context_items.append(f"\n--- DOCUMENT: {doc_name} ---")
            
            res = search_documents(query_embedding, [doc_id], n_results=5)
            r_docs = res.get("documents", [[]])[0]
            r_metas = res.get("metadatas", [[]])[0]
            r_dists = res.get("distances", [[]])[0]
            
            scored = []
            for d, m, dist in zip(r_docs, r_metas, r_dists):
                score = normalize_l2_to_relevance(dist)
                if score >= MIN_DOC_RELEVANCE: scored.append((score, d, m))
                
            scored.sort(key=lambda x: x[0], reverse=True)
            for score, d, m in scored[:4]:
                candidate_documents.append(d)
                candidate_metadatas.append(m)
                candidate_scores.append(score)
                loc_str = f"Page {m.get('page')}" if m.get('page') else (f"Slide {m.get('slide')}" if m.get('slide') else f"Chunk {global_chunk_idx}")
                doc_context_items.append(f"[Doc Chunk {global_chunk_idx}] (From: {doc_name}, {loc_str}):\n{d}")
                global_chunk_idx += 1
                
    elif not candidate_documents and intent in ["EXACT_LOOKUP", "STRUCTURED_LOOKUP", "COUNT_AGGREGATION", "TABLE_QUERY", "DOCUMENT_LOOKUP", "MULTI_DOCUMENT_QA", "MIXED_DOCUMENT_AND_WEB", "HYBRID", "SEMANTIC_QA"]:
        try:
            # 1a. Exact Keyword Match using Full Document Scanner (Structured Record DB)
            from ai.exact_lookup import extract_exact_records
            
            keywords_to_try = []
            if entity_name and len(entity_name) >= 1:
                keywords_to_try.append(entity_name)
                keywords_to_try.extend(extract_search_keywords(entity_name))
            
            keywords_to_try.extend(extract_search_keywords(search_query))
            
            seen_kw = set()
            unique_keywords = []
            for kw in keywords_to_try:
                kw_lower = kw.lower()
                if kw_lower not in seen_kw and len(kw) >= 1:
                    unique_keywords.append(kw)
                    seen_kw.add(kw_lower)
                    
            seen_chunks = set()
            
            if unique_keywords:
                exact_res = extract_exact_records(unique_keywords, document_ids, max_records=15)
                e_docs = exact_res.get("documents", [])
                e_metas = exact_res.get("metadatas", [])
                
                for doc, meta in zip(e_docs, e_metas):
                    doc_hash = hash(doc)
                    if doc_hash not in seen_chunks:
                        candidate_documents.append(doc)
                        candidate_metadatas.append(meta)
                        candidate_scores.append(1.0) # Exact match gets max score
                        seen_chunks.add(doc_hash)

            # 1b. Semantic Match (Always run to supplement exact matches)
            query_embedding = generate_embeddings([search_query])[0]
            results = search_documents(query_embedding, document_ids, n_results=12)
            raw_docs = results.get("documents", [[]])[0]
            raw_metas = results.get("metadatas", [[]])[0]
            raw_distances = results.get("distances", [[]])[0]
            
            scored_candidates = []
            for doc, meta, dist in zip(raw_docs, raw_metas, raw_distances):
                score = normalize_l2_to_relevance(dist)
                # Append all returned chunks. ChromaDB already returns the closest n_results.
                # Unnormalized embeddings cause large distances, so we shouldn't hard-filter.
                scored_candidates.append((score, doc, meta))
            
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            for score, doc, meta in scored_candidates[:10]: # Take top 10 chunks unconditionally
                doc_hash = hash(doc)
                if doc_hash not in seen_chunks:
                    candidate_documents.append(doc)
                    candidate_metadatas.append(meta)
                    candidate_scores.append(score)
                    seen_chunks.add(doc_hash)
                    
            # Trim total context size to prevent overflow (up to 20 chunks)
            if len(candidate_documents) > 20:
                candidate_documents = candidate_documents[:20]
                candidate_metadatas = candidate_metadatas[:20]
                candidate_scores = candidate_scores[:20]
            
            if intent == "MIXED_DOCUMENT_AND_WEB" and candidate_scores and max(candidate_scores) >= STRONG_DOC_THRESHOLD:
                print(f"[RAG Pipeline] Found strong doc match. Downgrading MIXED to DOCUMENT_LOOKUP.")
                intent = "DOCUMENT_LOOKUP"
        except Exception as e:
            print(f"[RAG Warning] Vector retrieval error: {e}")

    # Build context strings if not already built by comparison logic
    if not doc_context_items:
        for i, (doc, meta) in enumerate(zip(candidate_documents, candidate_metadatas), 1):
            loc_str = f"Page {meta.get('page')}" if meta.get('page') else (f"Slide {meta.get('slide')}" if meta.get('slide') else f"Chunk {i}")
            fn = meta.get('filename', 'Unknown Document')
            doc_context_items.append(f"[Doc Chunk {i}] (From: {fn}, {loc_str}):\n{doc}")

    doc_context = "\n\n".join(doc_context_items) if doc_context_items else "No relevant document text found."

    # ============================================
    # 2. Web Search (Strictly Gated)
    # ============================================
    if intent in ["WEB_ONLY", "MIXED_DOCUMENT_AND_WEB", "GENERAL_KNOWLEDGE"]:
        try:
            raw_web_results = search_web(search_query, max_results=8)
            if not raw_web_results and search_query != question:
                raw_web_results = search_web(question, max_results=8)
            topic_to_match = entity_name if entity_name else search_query
            web_results = filter_web_results(raw_web_results, topic_to_match, min_relevance=MIN_WEB_RELEVANCE)
        except Exception as e:
            print(f"[RAG Warning] Web search error: {e}")

    # ============================================
    # 3. Handle Complete Failure (Removed to allow LLM to handle conversational/empty context natively)
    # ============================================
    web_context_items = []
    if web_results:
        for i, item in enumerate(web_results, 1): web_context_items.append(f"[{i}] {item['title']} ({item['url']}):\n{item['snippet']}")
        web_context = "\n\n".join(web_context_items)
    else: web_context = "No external web results available."

    # ============================================
    # 4. Prompt & Generation
    # ============================================
    prompt = f"""
{SYSTEM_PROMPT}

Previous Conversation:
{history_text if history_text else "None"}

Uploaded Document Context:
{doc_context}

Web Search Context:
{web_context}

Current User Question:
{question}

Resolved Search Query:
{search_query}

Answer:
"""

    raw_answer = generate_answer(prompt)

    cited_indices = []
    match = re.search(r'CITED_CHUNKS:\s*\[(.*?)\]', raw_answer, re.IGNORECASE)
    if match:
        indices_str = match.group(1).strip()
        if indices_str:
            for num in indices_str.split(','):
                num = num.strip()
                if num.isdigit(): cited_indices.append(int(num))
        clean_answer = re.sub(r'CITED_CHUNKS:\s*\[.*?\]', '', raw_answer, flags=re.IGNORECASE).strip()
        clean_answer = re.sub(r'USED_WEB_SEARCH:\s*(YES|NO)', '', clean_answer, flags=re.IGNORECASE).strip()
    else:
        clean_answer = raw_answer.strip()
        for i, doc in enumerate(candidate_documents, 1):
            if semantic_overlap_check(doc, clean_answer): cited_indices.append(i)

    clean_answer = re.sub(r'^#+\s+', '', clean_answer, flags=re.MULTILINE)
    clean_answer = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_answer)
    clean_answer = re.sub(r'\*(.*?)\*', r'\1', clean_answer)
    clean_answer = re.sub(r'__(.*?)__', r'\1', clean_answer)
    clean_answer = re.sub(r'_(.*?)_', r'\1', clean_answer)
    clean_answer = re.sub(r'`(.*?)`', r'\1', clean_answer)
    clean_answer = re.sub(r'^>\s+', '', clean_answer, flags=re.MULTILINE)
    clean_answer = re.sub(r'~~(.*?)~~', r'\1', clean_answer)
    clean_answer = clean_answer.strip()

    # ============================================
    # 5. Citation Validation
    # ============================================
    unique_doc_sources = {}
    for i, (doc, meta) in enumerate(zip(candidate_documents, candidate_metadatas), 1):
        if cited_indices and i not in cited_indices: continue
        if not semantic_overlap_check(doc, clean_answer): continue

        source_obj = format_document_source(meta)
        if not source_obj.get("filename") or not source_obj.get("url"): continue
            
        key = (source_obj["document_id"], source_obj["filename"], source_obj["location_type"], source_obj["location"])
        if key not in unique_doc_sources: unique_doc_sources[key] = source_obj

    document_sources = list(unique_doc_sources.values())

    unique_web_sources = {}
    if web_results and intent in ["WEB_ONLY", "MIXED_DOCUMENT_AND_WEB", "GENERAL_KNOWLEDGE"]:
        for item in web_results:
            raw_url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            if not raw_url or not title or raw_url == "undefined" or title == "undefined": continue
            if raw_url not in unique_web_sources:
                unique_web_sources[raw_url] = {
                    "type": "web", "title": title or item.get("domain", "Web Source"), "url": raw_url,
                    "domain": item.get("domain", ""), "label": f"{title} ({item.get('domain', '')})"
                }

    web_sources = list(unique_web_sources.values())
    all_sources = document_sources + web_sources

    return {
        "answer": clean_answer,
        "document_sources": document_sources,
        "web_sources": web_sources,
        "sources": all_sources,
        "source": document_sources[0].get("source") if document_sources else None,
        "chunk": document_sources[0].get("chunk") if document_sources else None
    }