import json
import re
from ai.openai_chat import generate_answer
from ai.intelligence_prompts import (
    TOPICS_PROMPT, VIVA_PROMPT, FIVE_MARK_PROMPT, MCQ_PROMPT,
    SUMMARY_PROMPT, FLASHCARDS_PROMPT, REVISION_PROMPT, IMPORTANT_TOPICS_PROMPT
)
from ai.vector_store import get_all_document_chunks_unlimited
from ai.rag_pipeline import format_document_source

MAX_SAFE_CHARS = 240000  # roughly 60,000 tokens

def build_context(document_ids):
    res = get_all_document_chunks_unlimited(document_ids)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    
    if not docs:
        return "", []

    total_chars = sum(len(d) for d in docs)
    if total_chars > MAX_SAFE_CHARS:
        return "TOO_LARGE", metas

    context_str = ""
    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
        context_str += f"[Doc Chunk {i}]\n{doc}\n\n"
        
    return context_str, metas

def build_chunk_groups(document_ids, chars_per_group=120000):
    res = get_all_document_chunks_unlimited(document_ids)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    
    if not docs:
        return []
        
    groups = []
    current_group_text = ""
    current_group_metas = []
    current_chars = 0
    
    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
        chunk_text = f"[Doc Chunk {i}]\n{doc}\n\n"
        if current_chars + len(chunk_text) > chars_per_group and current_group_text:
            groups.append((current_group_text, current_group_metas))
            current_group_text = chunk_text
            current_group_metas = [meta]
            current_chars = len(chunk_text)
        else:
            current_group_text += chunk_text
            current_group_metas.append(meta)
            current_chars += len(chunk_text)
            
    if current_group_text:
        groups.append((current_group_text, current_group_metas))
        
    return groups

def extract_json(text):
    text = text.strip()
    match = re.search(r'```(?:json)?\s*(\{.*\}|\[.*\])\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    else:
        start_brace = text.find('{')
        end_brace = text.rfind('}')
        start_bracket = text.find('[')
        end_bracket = text.rfind(']')
        
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            text = text[start_brace:end_brace+1]
        elif start_bracket != -1:
            text = text[start_bracket:end_bracket+1]
            
    text = text.strip()
    return json.loads(text)

def map_citations(result_json, metas):
    if isinstance(result_json, dict) and "questions" in result_json:
        for q in result_json["questions"]:
            cited_indices = q.get("cited_chunks", [])
            sources = []
            unique_keys = set()
            for idx in cited_indices:
                if 1 <= idx <= len(metas):
                    meta = metas[idx - 1]
                    src = format_document_source(meta)
                    if src.get("filename"):
                        key = (src["document_id"], src["location_type"], src["location"])
                        if key not in unique_keys:
                            unique_keys.add(key)
                            sources.append(src)
            q["sources"] = sources
    return result_json

def process_adaptive(document_ids, base_prompt, fallback_key=""):
    context, metas = build_context(document_ids)
    
    if not context:
        return {fallback_key: []} if fallback_key else {}
        
    if context == "TOO_LARGE":
        # Map-reduce approach
        groups = build_chunk_groups(document_ids)
        intermediate_results = []
        
        for g_text, g_meta in groups:
            prompt = f"{base_prompt}\n\nDocument Context:\n{g_text}"
            try:
                res = generate_answer(prompt)
                extracted = extract_json(res)
                if fallback_key and fallback_key in extracted:
                    intermediate_results.extend(extracted[fallback_key])
                elif isinstance(extracted, dict):
                    intermediate_results.append(str(extracted))
            except Exception as e:
                print(f"Map phase error: {e}")
                
        # Reduce phase
        if fallback_key:
            # If it's a list based output like flashcards or topics, just combine them directly, 
            # or optionally ask LLM to deduplicate. For speed, we just return the combined list.
            return {fallback_key: intermediate_results}
        else:
            # For summary/revision notes, ask LLM to synthesize the intermediate parts
            synthesis_prompt = f"{base_prompt}\n\nHere are partial outputs from sections of the document. Synthesize them into one final comprehensive JSON response matching the schema.\n\nPartial Outputs:\n"
            for i, part in enumerate(intermediate_results):
                synthesis_prompt += f"--- Part {i+1} ---\n{part}\n\n"
                
            final_res = generate_answer(synthesis_prompt)
            try:
                return extract_json(final_res)
            except:
                return {}
    else:
        # Standard approach for small/medium documents
        prompt = f"{base_prompt}\n\nDocument Context:\n{context}"
        raw_answer = generate_answer(prompt)
        try:
            return extract_json(raw_answer)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return {fallback_key: []} if fallback_key else {}

def extract_topics(document_id):
    return process_adaptive([document_id], TOPICS_PROMPT, "topics")

def generate_summary(document_ids):
    return process_adaptive(document_ids, SUMMARY_PROMPT, "summary")

def generate_flashcards(document_ids):
    return process_adaptive(document_ids, FLASHCARDS_PROMPT, "flashcards")

def generate_revision_notes(document_ids):
    return process_adaptive(document_ids, REVISION_PROMPT, "")

def generate_important_topics(document_ids):
    return process_adaptive(document_ids, IMPORTANT_TOPICS_PROMPT, "important_topics")

def generate_exam_prep(document_id, exam_type, difficulty, count=3):
    context, metas = build_context([document_id])
    if not context:
        return {"questions": []}
        
    if exam_type == "viva":
        base_prompt = VIVA_PROMPT
    elif exam_type == "5mark":
        base_prompt = FIVE_MARK_PROMPT
    elif exam_type == "mcq":
        base_prompt = MCQ_PROMPT
    else:
        return {"questions": []}
        
    formatted_prompt = base_prompt.replace("{difficulty}", difficulty).replace("{count}", str(count))
    
    # For exams, if too large, we just map-reduce and concatenate questions until we hit the count
    if context == "TOO_LARGE":
        groups = build_chunk_groups([document_id])
        all_questions = []
        for g_text, g_meta in groups:
            if len(all_questions) >= count:
                break
            prompt = f"{formatted_prompt}\n\nDocument Context:\n{g_text}"
            try:
                raw_answer = generate_answer(prompt)
                data = extract_json(raw_answer)
                mapped = map_citations(data, g_meta)
                if "questions" in mapped:
                    all_questions.extend(mapped["questions"])
            except:
                pass
        return {"questions": all_questions[:count]}
    else:
        prompt = f"{formatted_prompt}\n\nDocument Context:\n{context}"
        raw_answer = generate_answer(prompt)
        try:
            data = extract_json(raw_answer)
            return map_citations(data, metas)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return {"questions": []}
