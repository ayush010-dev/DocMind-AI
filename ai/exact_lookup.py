import json
from database.database import SessionLocal
from database import models
from sqlalchemy import or_

def extract_exact_records(keywords, document_ids, max_records=15):
    db = SessionLocal()
    try:
        query = db.query(models.DocumentRecord).filter(
            models.DocumentRecord.document_id.in_(document_ids)
        )
        
        if keywords:
            conditions = []
            for kw in keywords:
                search_term = f"%{kw}%"
                conditions.append(models.DocumentRecord.content.ilike(search_term))
            
            query = query.filter(or_(*conditions))
            
        records = query.limit(max_records).all()
        
        documents = []
        metadatas = []
        for r in records:
            documents.append(r.content)
            try:
                meta = json.loads(r.metadata_json) if r.metadata_json else {}
            except Exception:
                meta = {}
            meta["page"] = r.page_number
            meta["document_id"] = r.document_id
            metadatas.append(meta)
            
        return {
            "documents": documents,
            "metadatas": metadatas
        }
    except Exception as e:
        print(f"[Exact Lookup Error] {e}")
        return {"documents": [], "metadatas": []}
    finally:
        db.close()
