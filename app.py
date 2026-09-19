# pyrefly: ignore [missing-import]
import os
os.environ["HF_HUB_OFFLINE"] = "1"

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    Request,
    HTTPException,
    Depends,
    BackgroundTasks
)

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

import os
import shutil
import uuid
import traceback
import json

from database.database import engine, Base, SessionLocal
from database import models

from readers.document_router import read_document
from ai.text_chunker import chunk_text
from ai.embedding_generator import generate_embeddings
from ai.vector_store import store_embeddings, search_documents_exact
from ai.rag_pipeline import ask_document
from ai.intelligence import extract_topics, generate_exam_prep, generate_summary, generate_flashcards, generate_revision_notes, generate_important_topics


# =====================================================
# Database
# =====================================================

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =====================================================
# FastAPI
# =====================================================

app = FastAPI(
    title="DocMind AI",
    description="AI Powered Document Chatbot using RAG",
    version="1.0.0"
)


# =====================================================
# Static Files & Templates
# =====================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(
    directory="templates"
)


# =====================================================
# Upload Configuration
# =====================================================

UPLOAD_FOLDER = "uploads"
DOCUMENTS_FOLDER = "documents"

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".txt"
}

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    DOCUMENTS_FOLDER,
    exist_ok=True
)


# =====================================================
# Request Models
# =====================================================

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    document_ids: list[str] = Field(default_factory=list)

    chat_id: int | None = None

    chat_history: list[ChatMessage] = Field(
        default_factory=list
    )

class IntelligenceRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)



# =====================================================
# Home
# =====================================================

@app.get("/")
def home(request: Request):

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request
        }
    )


# =====================================================
# Background Processing Task
# =====================================================

def process_document_background(file_path: str, filename: str, document_id: str):
    db = SessionLocal()
    try:
        # Extract Text
        blocks = read_document(file_path)
        has_text = False
        if isinstance(blocks, list):
            has_text = any(isinstance(b, dict) and b.get("text", "").strip() for b in blocks)
        elif isinstance(blocks, str):
            has_text = bool(blocks.strip())

        if not blocks or not has_text:
            raise ValueError("No readable text found in document.")

        # Create Chunks
        chunk_data = chunk_text(blocks)
        semantic_chunks = chunk_data.get("semantic_chunks", [])
        exact_records = chunk_data.get("exact_records", [])

        if not semantic_chunks and not exact_records:
            raise ValueError("Failed to create document chunks.")

        # Generate Embeddings for Semantic Chunks
        if semantic_chunks:
            embeddings = generate_embeddings(semantic_chunks)
            store_embeddings(
                chunks=semantic_chunks,
                embeddings=embeddings,
                file_name=filename,
                document_id=document_id
            )

        # Store Exact Records in SQLite DocumentRecord
        for record in exact_records:
            meta_json = json.dumps(record.get("metadata", {}))
            page_num = record.get("metadata", {}).get("page")
            extraction_method = record.get("metadata", {}).get("extraction_method", "parser")
            
            db_record = models.DocumentRecord(
                document_id=document_id,
                page_number=page_num,
                record_id=record["record_id"],
                content=record["text"],
                normalized_content=record["normalized_text"],
                extraction_method=extraction_method,
                metadata_json=meta_json
            )
            db.add(db_record)
        db.commit()

        # Move to Persistent Storage
        doc_dir = os.path.join(DOCUMENTS_FOLDER, document_id)
        os.makedirs(doc_dir, exist_ok=True)
        persistent_path = os.path.join(doc_dir, filename)
        shutil.move(file_path, persistent_path)
        file_path = None # Prevent deletion in finally block

        # Update Document Status
        doc = db.query(models.Document).filter(models.Document.chroma_id == document_id).first()
        if doc:
            doc.status = "ready"
            db.commit()

    except Exception as e:
        traceback.print_exc()
        doc = db.query(models.Document).filter(models.Document.chroma_id == document_id).first()
        if doc:
            doc.status = "failed"
            err_msg = str(e)
            if "INVALID_API_KEY" in err_msg:
                doc.error_message = "Invalid API Key. Please check your .env file."
            elif "AI_SERVICE_BUSY" in err_msg:
                doc.error_message = "The AI service is temporarily busy. Please try again in a moment."
            else:
                doc.error_message = err_msg
            db.commit()
    finally:
        db.close()
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


# =====================================================
# Upload Document
# =====================================================

@app.post("/upload")
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chat_id: int | None = Form(None),
    db: Session = Depends(get_db)
):

    file_path = None

    try:

        # ---------------------------------------------
        # Validate File
        # ---------------------------------------------

        if not file.filename:

            raise HTTPException(
                status_code=400,
                detail="No file selected."
            )

        extension = os.path.splitext(
            file.filename
        )[1].lower()

        if extension not in ALLOWED_EXTENSIONS:

            raise HTTPException(
                status_code=400,
                detail="Unsupported file type."
            )


        # ---------------------------------------------
        # Save Temporary File
        # ---------------------------------------------

        unique_filename = (
            f"{uuid.uuid4()}_{file.filename}"
        )

        file_path = os.path.join(
            UPLOAD_FOLDER,
            unique_filename
        )

        with open(file_path, "wb") as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

        # ---------------------------------------------
        # Create Chroma Document ID
        # ---------------------------------------------

        document_id = str(
            uuid.uuid4()
        )

        # ---------------------------------------------
        # Save Document in SQLite
        # ---------------------------------------------

        document = models.Document(
            filename=file.filename,
            chroma_id=document_id,
            status="processing"
        )

        db.add(document)

        db.commit()

        db.refresh(document)

        # ---------------------------------------------
        # Create or Update Chat
        # ---------------------------------------------

        if chat_id:
            chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
            if not chat:
                raise HTTPException(status_code=404, detail="Chat not found.")
            chat.documents.append(document)
            db.commit()
            db.refresh(chat)
        else:
            chat = models.Chat(
                title=file.filename
            )
            chat.documents.append(document)
            db.add(chat)
            db.commit()
            db.refresh(chat)

        # ---------------------------------------------
        # Start Background Processing
        # ---------------------------------------------
        
        background_tasks.add_task(
            process_document_background, 
            file_path, 
            file.filename, 
            document_id
        )
        
        # Don't delete in the upload endpoint's finally block if we passed it to background
        file_path_for_cleanup = None

        # ---------------------------------------------
        # Return Response
        # ---------------------------------------------

        return {

            "message":
            "Upload started...",

            "filename":
            file.filename,

            "document_id":
            document_id,

            "chat_id":
            chat.id,
            
            "status": "processing"
        }


    except HTTPException:

        db.rollback()

        raise


    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Upload Failed: Something went wrong on our end. Please try again."
        )


    finally:

        # We use a local reference since file_path is passed to background task
        # If an error happens before background_tasks.add_task, file_path_for_cleanup won't be None
        cleanup_path = locals().get('file_path_for_cleanup', file_path)
        if cleanup_path and os.path.exists(cleanup_path):

            try:
                os.remove(cleanup_path)
            except Exception:
                pass


# =====================================================
# Document Status Endpoint
# =====================================================

@app.get("/documents/{document_id}/status")
def get_document_status(
    document_id: str,
    db: Session = Depends(get_db)
):
    doc = db.query(models.Document).filter(models.Document.chroma_id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    return {
        "status": doc.status,
        "error_message": doc.error_message
    }


# =====================================================
# Chat
# =====================================================

@app.post("/chat")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):

    try:

        # ---------------------------------------------
        # Validate Question
        # ---------------------------------------------

        question = request.question.strip()

        if not question:

            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty."
            )


        # ---------------------------------------------
        # Validate Document IDs
        # ---------------------------------------------

        if not request.document_ids:

            raise HTTPException(
                status_code=400,
                detail="At least one Document ID is required."
            )


        # ---------------------------------------------
        # Find Chat
        # ---------------------------------------------

        chat_record = None

        if request.chat_id is not None:

            chat_record = (
                db.query(models.Chat)
                .filter(
                    models.Chat.id == request.chat_id
                )
                .first()
            )


        if not chat_record:

            documents = (
                db.query(models.Document)
                .filter(models.Document.chroma_id.in_(request.document_ids))
                .all()
            )

            if not documents:

                raise HTTPException(
                    status_code=404,
                    detail="Documents not found."
                )

            try:
                from ai.openai_chat import generate_answer
                title_prompt = f"Create a short title (maximum 4 words) for this chat starting with: {question}\nReturn ONLY the title."
                title = generate_answer(title_prompt).strip()
                title = title.replace('"', '').replace("'", "")
            except:
                title = question[:30]

            chat_record = models.Chat(
                title=title
            )
            
            chat_record.documents.extend(documents)

            db.add(chat_record)

            db.commit()

            db.refresh(chat_record)


        # ---------------------------------------------
        # Save User Message
        # ---------------------------------------------

        user_message = models.Message(
            chat_id=chat_record.id,
            role="user",
            content=question
        )

        db.add(user_message)

        db.commit()


        # ---------------------------------------------
        # Prepare Chat History
        # ---------------------------------------------

        previous_messages = (
            db.query(models.Message)
            .filter(models.Message.chat_id == chat_record.id)
            .order_by(models.Message.created_at.asc())
            .all()
        )

        chat_history = [
            {
                "role": message.role,
                "content": message.content
            }
            for message in previous_messages
        ]


        active_docs = [
            {"document_id": doc.chroma_id, "filename": doc.filename, "uploaded_at": doc.uploaded_at.isoformat()}
            for doc in chat_record.documents
            if doc.chroma_id in request.document_ids
        ]

        # ---------------------------------------------
        # RAG
        # ---------------------------------------------

        response = ask_document(

            question=question,

            active_documents=active_docs,

            chat_history=chat_history

        )


        # ---------------------------------------------
        # Save AI Response
        # ---------------------------------------------

        answer = response.get(
            "answer",
            "I couldn't generate an answer."
        )

        doc_sources = response.get("document_sources", [])
        web_sources = response.get("web_sources", [])
        all_sources = response.get("sources", [])

        sources_payload = {
            "document_sources": doc_sources,
            "web_sources": web_sources,
            "sources": all_sources
        }

        assistant_message = models.Message(
            chat_id=chat_record.id,
            role="assistant",
            content=answer,
            sources=json.dumps(sources_payload)
        )

        db.add(assistant_message)

        db.commit()


        # ---------------------------------------------
        # Return Response
        # ---------------------------------------------

        return {

            "question":
            question,

            "answer":
            answer,
            
            "document_sources":
            doc_sources,

            "web_sources":
            web_sources,

            "sources":
            all_sources,

            "source":
            response.get("source"),

            "chunk":
            response.get("chunk"),

            "chat_id":
            chat_record.id
        }


    except HTTPException:

        db.rollback()

        raise


    except Exception as e:
        db.rollback()
        traceback.print_exc()
        error_msg = str(e)
        if "INVALID_API_KEY" in error_msg:
             raise HTTPException(status_code=401, detail="Invalid API Key. Please check your .env file.")
        if "AI_SERVICE_BUSY" in error_msg or "rate limit" in error_msg.lower() or "overloaded" in error_msg.lower() or "503" in error_msg:
             safe_detail = "The AI service is temporarily busy. Please try again in a moment."
        else:
             safe_detail = "Something went wrong on our end. Please try again."

        raise HTTPException(
            status_code=500,
            detail=safe_detail
        )
        
# =====================================================
# Get Chat History
# =====================================================

@app.get("/chats")
def get_chats(
    db: Session = Depends(get_db)
):

    try:

        chats = (
            db.query(models.Chat)
            .order_by(
                models.Chat.created_at.desc()
            )
            .all()
        )

        return [
            {
                "id": chat.id,
                "title": chat.title,
                "documents": [
                    {
                        "document_id": doc.chroma_id,
                        "filename": doc.filename
                    }
                    for doc in chat.documents
                ],
                "created_at": chat.created_at
            }
            for chat in chats
        ]

    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to load chats: {str(e)}"
        )


# =====================================================
# Get Single Chat
# =====================================================

@app.get("/chats/{chat_id}")
def get_chat(
    chat_id: int,
    db: Session = Depends(get_db)
):

    try:

        chat = (
            db.query(models.Chat)
            .filter(
                models.Chat.id == chat_id
            )
            .first()
        )

        if not chat:

            raise HTTPException(
                status_code=404,
                detail="Chat not found."
            )

        messages = (
            db.query(models.Message)
            .filter(
                models.Message.chat_id == chat_id
            )
            .order_by(
                models.Message.created_at.asc()
            )
            .all()
        )

        formatted_messages = []
        for message in messages:
            doc_srcs = []
            web_srcs = []
            all_srcs = []

            if getattr(message, "sources", None):
                try:
                    parsed_srcs = json.loads(message.sources)
                    if isinstance(parsed_srcs, dict):
                        doc_srcs = parsed_srcs.get("document_sources", [])
                        web_srcs = parsed_srcs.get("web_sources", [])
                        all_srcs = parsed_srcs.get("sources", doc_srcs + web_srcs)
                    elif isinstance(parsed_srcs, list):
                        doc_srcs = [s for s in parsed_srcs if isinstance(s, dict) and s.get("type") != "web"]
                        web_srcs = [s for s in parsed_srcs if isinstance(s, dict) and s.get("type") == "web"]
                        all_srcs = parsed_srcs
                except Exception:
                    pass

            formatted_messages.append({
                "role": message.role,
                "content": message.content,
                "document_sources": doc_srcs,
                "web_sources": web_srcs,
                "sources": all_srcs,
                "created_at": message.created_at
            })

        return {

            "chat_id": chat.id,

            "title": chat.title,

            "documents": [
                {
                    "document_id": doc.chroma_id,
                    "filename": doc.filename
                }
                for doc in chat.documents
            ],

            "messages": formatted_messages
        }

    except HTTPException:

        raise

    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to load chat: {str(e)}"
        )


# =====================================================
# Delete Chat
# =====================================================

@app.delete("/chats/{chat_id}")
def delete_chat(
    chat_id: int,
    db: Session = Depends(get_db)
):

    try:

        chat = (
            db.query(models.Chat)
            .filter(
                models.Chat.id == chat_id
            )
            .first()
        )

        if not chat:

            raise HTTPException(
                status_code=404,
                detail="Chat not found."
            )

        db.delete(chat)
        db.commit()

        return {"message": "Chat deleted successfully."}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete chat: {str(e)}"
        )


# =====================================================
# Delete Document (Global)
# =====================================================

@app.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    try:
        # Find document
        doc = db.query(models.Document).filter(models.Document.chroma_id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        # Delete chats only if they have no other documents associated
        chats_to_delete = []
        for chat in doc.chats:
            if len(chat.documents) <= 1:
                chats_to_delete.append(chat)
                
        for chat in chats_to_delete:
            db.delete(chat)
            
        # Delete document from SQLite
        db.delete(doc)
        db.commit()

        # Delete from ChromaDB
        try:
            from ai.vector_store import collection
            collection.delete(where={"document_id": document_id})
        except Exception as e:
            print(f"Warning: Failed to delete from ChromaDB: {e}")

        # Delete from filesystem
        doc_dir = os.path.join(DOCUMENTS_FOLDER, document_id)
        if os.path.exists(doc_dir):
            import shutil
            try:
                shutil.rmtree(doc_dir)
            except Exception as e:
                print(f"Warning: Failed to delete physical files: {e}")

        return {"message": "Document and associated chats deleted successfully."}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


# =====================================================
# Search Chats / Documents
# =====================================================

@app.get("/search")
def search(
    q: str,
    db: Session = Depends(get_db)
):
    try:
        from sqlalchemy import or_
        query = f"%{q}%"

        # Search Chats
        chats = (
            db.query(models.Chat)
            .join(models.Document)
            .outerjoin(models.Message)
            .filter(
                or_(
                    models.Chat.title.ilike(query),
                    models.Document.filename.ilike(query),
                    models.Message.content.ilike(query)
                )
            )
            .distinct()
            .all()
        )

        return [
            {
                "id": chat.id,
                "title": chat.title,
                "document_id": chat.document.chroma_id if chat.document else None,
                "filename": chat.document.filename if chat.document else None
            }
            for chat in chats
        ]

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

# =====================================================
# Get All Documents
# =====================================================

@app.get("/documents")
def get_documents(
    db: Session = Depends(get_db)
):
    try:
        documents = (
            db.query(models.Document)
            .order_by(models.Document.uploaded_at.desc())
            .all()
        )
        return [
            {
                "id": doc.id,
                "chroma_id": doc.chroma_id,
                "filename": doc.filename,
                "uploaded_at": doc.uploaded_at
            }
            for doc in documents
        ]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch documents: {str(e)}"
        )


# =====================================================
# Serve Document Source
# =====================================================

from fastapi.responses import FileResponse

@app.get("/documents/{document_id}/source")
def get_document_source(
    document_id: str,
    db: Session = Depends(get_db)
):
    document = (
        db.query(models.Document)
        .filter(models.Document.chroma_id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    file_path = os.path.join(
        DOCUMENTS_FOLDER,
        document_id,
        document.filename
    )

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Document file not found on server."
        )

    return FileResponse(file_path)

# =====================================================
# Document Intelligence
# =====================================================

@app.post("/intelligence/summary")
def api_generate_summary(req: IntelligenceRequest):
    try:
        return generate_summary(req.document_ids)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate summary.")

@app.post("/intelligence/flashcards")
def api_generate_flashcards(req: IntelligenceRequest):
    try:
        return generate_flashcards(req.document_ids)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate flashcards.")

@app.post("/intelligence/revision")
def api_generate_revision_notes(req: IntelligenceRequest):
    try:
        return generate_revision_notes(req.document_ids)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate revision notes.")

@app.post("/intelligence/important")
def api_generate_important_topics(req: IntelligenceRequest):
    try:
        return generate_important_topics(req.document_ids)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate important topics.")

@app.get("/intelligence/{document_id}/topics")
def get_intelligence_topics(document_id: str):
    try:
        return extract_topics(document_id)
    except Exception as e:
        err_msg = str(e)
        if "INVALID_API_KEY" in err_msg:
            raise HTTPException(status_code=401, detail="Invalid API Key. Please check your .env file.")
        if "AI_SERVICE_BUSY" in err_msg or "503" in err_msg:
             raise HTTPException(status_code=503, detail="The AI service is temporarily busy. Please try again in a moment.")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate topics. Please try again.")

@app.get("/intelligence/{document_id}/exam")
def get_intelligence_exam(document_id: str, type: str, difficulty: str = "Medium", count: int = 3):
    try:
        if type not in ["viva", "5mark", "mcq"]:
            raise HTTPException(status_code=400, detail="Invalid exam type")
        return generate_exam_prep(document_id, type, difficulty, count)
    except Exception as e:
        err_msg = str(e)
        if "INVALID_API_KEY" in err_msg:
            raise HTTPException(status_code=401, detail="Invalid API Key. Please check your .env file.")
        if "AI_SERVICE_BUSY" in err_msg:
            raise HTTPException(status_code=503, detail="The AI service is temporarily busy. Please try again in a moment.")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="The AI service is temporarily busy. Please try again in a moment."
        )

@app.get("/intelligence/{document_id}/search")
def search_document_intelligence(document_id: str, q: str):
    try:
        results = search_documents_exact(q, [document_id])
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        
        matches = []
        for i, (doc_text, meta) in enumerate(zip(docs, metas)):
            matches.append({
                "text": doc_text,
                "metadata": meta
            })
            
        return {"matches": matches}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Search failed.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)