import os
import sys
import uuid
from sqlalchemy.orm import Session

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import SessionLocal
from database import models
from app import process_document_background
from ai.rag_pipeline import ask_document

def test_backend():
    test_pdf = os.path.join(os.path.dirname(__file__), "..", "uploads", "test_doc_verify.txt")
    with open(test_pdf, "w", encoding="utf-8") as f:
        f.write("Piyush with address B3/137 has serial number 698.\nAyush is his brother.\nTotal Electors = 716.\n")
        
    doc_id = str(uuid.uuid4())
    filename = "test_doc_verify.txt"
    
    db = SessionLocal()
    doc = models.Document(
        filename=filename,
        chroma_id=doc_id,
        status="processing"
    )
    db.add(doc)
    db.commit()
    db.close()
    
    print("Processing document...")
    process_document_background(test_pdf, filename, doc_id)
    
    db = SessionLocal()
    doc = db.query(models.Document).filter(models.Document.chroma_id == doc_id).first()
    print("Document status:", doc.status)
    if doc.status == "failed":
        print("Error:", doc.error_message)
        return
        
    active_docs = [{"document_id": doc_id, "filename": filename}]
    
    queries = [
        "Is there anyone named Piyush?",
        "What is Piyush's serial number?",
        "What is the total number of electors?",
        "What is Piyush's address?"
    ]
    
    for q in queries:
        print(f"\nQ: {q}")
        res = ask_document(q, active_documents=active_docs)
        print(f"A: {res['answer']}")

if __name__ == "__main__":
    test_backend()
