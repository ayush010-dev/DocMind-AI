from sqlalchemy.orm import Session

from . import models


# -------------------------
# Document CRUD
# -------------------------

def create_document(
    db: Session,
    filename: str
):
    document = models.Document(
        filename=filename
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def get_document(
    db: Session,
    document_id: int
):
    return db.query(models.Document).filter(
        models.Document.id == document_id
    ).first()

def remove_document_from_chat(
    db: Session,
    chat_id: int,
    document_id: int
):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        return False
        
    # Find the document in the chat's documents list
    doc_to_remove = next((doc for doc in chat.documents if doc.id == document_id), None)
    
    if doc_to_remove:
        chat.documents.remove(doc_to_remove)
        db.commit()
        return True
        
    return False


# -------------------------
# Chat CRUD
# -------------------------

def create_chat(
    db: Session,
    document_id: int,
    title: str
):
    chat = models.Chat(
        document_id=document_id,
        title=title
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    return chat


def get_chats(
    db: Session,
    document_id: int
):
    return db.query(models.Chat).filter(
        models.Chat.document_id == document_id
    ).order_by(
        models.Chat.created_at.desc()
    ).all()


# -------------------------
# Message CRUD
# -------------------------

def create_message(
    db: Session,
    chat_id: int,
    role: str,
    content: str
):
    message = models.Message(
        chat_id=chat_id,
        role=role,
        content=content
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


def get_messages(
    db: Session,
    chat_id: int
):
    return db.query(models.Message).filter(
        models.Message.chat_id == chat_id
    ).order_by(
        models.Message.created_at
    ).all()