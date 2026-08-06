from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Request,
    HTTPException
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import os
import shutil
import uuid
import traceback

from readers.document_router import read_document
from ai.text_chunker import chunk_text
from ai.embedding_generator import generate_embeddings
from ai.vector_store import store_embeddings
from ai.rag_pipeline import ask_document


# =====================================================
# FastAPI App
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
# Constants
# =====================================================

UPLOAD_FOLDER = "uploads"

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


# =====================================================
# Request Models
# =====================================================

class ChatRequest(BaseModel):
    question: str
    document_id: str


# =====================================================
# Home Route
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
# Upload API
# =====================================================

@app.post("/upload")
def upload_document(file: UploadFile = File(...)):

    try:

        # -----------------------------
        # Validate Extension
        # -----------------------------

        extension = os.path.splitext(
            file.filename
        )[1].lower()

        if extension not in ALLOWED_EXTENSIONS:

            raise HTTPException(
                status_code=400,
                detail="Unsupported file type."
            )

        # -----------------------------
        # Save File
        # -----------------------------

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

        # -----------------------------
        # Extract Text
        # -----------------------------

        document_text = read_document(file_path)

        if not document_text.strip():

            os.remove(file_path)

            raise HTTPException(
                status_code=400,
                detail="No text found in document."
            )

        # -----------------------------
        # Chunk Text
        # -----------------------------

        chunks = chunk_text(document_text)

        if len(chunks) == 0:

            os.remove(file_path)

            raise HTTPException(
                status_code=400,
                detail="Failed to create text chunks."
            )

        # -----------------------------
        # Generate Embeddings
        # -----------------------------

        embeddings = generate_embeddings(
            chunks
        )

        # -----------------------------
        # Generate Document ID
        # -----------------------------

        document_id = str(
            uuid.uuid4()
        )

        # -----------------------------
        # Store in ChromaDB
        # -----------------------------

        store_embeddings(
            chunks=chunks,
            embeddings=embeddings,
            file_name=file.filename,
            document_id=document_id
        )

        # Optional
        # Delete uploaded file after indexing

        os.remove(file_path)

        return {

            "message":
            "Document indexed successfully.",

            "filename":
            file.filename,

            "document_id":
            document_id,

            "chunks":
            len(chunks)

        }

    except HTTPException:

        raise

    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )


# =====================================================
# Chat API
# =====================================================

@app.post("/chat")
def chat(request: ChatRequest):

    try:

        response = ask_document(

            request.question,

            request.document_id

        )

        return {

            "question":
            request.question,

            "answer":
            response["answer"],

            "source":
            response["source"],

            "chunk":
            response["chunk"]

        }

    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Chat Failed: {str(e)}"
        )