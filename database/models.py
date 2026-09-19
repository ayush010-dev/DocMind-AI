from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base

chat_documents = Table(
    "chat_documents",
    Base.metadata,
    Column("chat_id", Integer, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
)


class Document(Base):

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    chroma_id = Column(String, unique=True, index=True, nullable=False)

    filename = Column(String, nullable=False)

    uploaded_at = Column(
        DateTime,
        server_default=func.now()
    )

    status = Column(String, default="processing")

    error_message = Column(String, nullable=True)

    chats = relationship(
        "Chat",
        secondary=chat_documents,
        back_populates="documents"
    )


class Chat(Base):

    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    documents = relationship(
        "Document",
        secondary=chat_documents,
        back_populates="chats"
    )

    messages = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete"
    )


class Message(Base):

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)

    chat_id = Column(
        Integer,
        ForeignKey("chats.id"),
        nullable=False
    )

    role = Column(String, nullable=False)

    content = Column(Text, nullable=False)

    sources = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    chat = relationship(
        "Chat",
        back_populates="messages"
    )

class DocumentRecord(Base):
    __tablename__ = "document_records"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, index=True, nullable=False) # chroma_id of Document
    page_number = Column(Integer, nullable=True)
    record_id = Column(String, index=True, nullable=False) # logical block id
    content = Column(Text, nullable=False)
    normalized_content = Column(Text, index=True, nullable=False)
    extraction_method = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)