"""Database models for Curio2 application.

This module contains SQLAlchemy models and Base declarative.
Separated from app.py to avoid circular imports during Alembic migrations.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Conversation(Base):
    """Conversation model representing a chat session with a user."""

    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    image_path = Column(String)
    phenomenon = Column(String)
    # User information from authentication system (optional, for logged-in users)
    user_id = Column(String)  # From JWT payload.sub
    user_email = Column(String)  # From JWT payload.email
    username = Column(String)  # From JWT payload.preferred_username or payload.name
    user_groups = Column(Text)  # JSON string of groups from JWT payload.groups
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime)
    evaluation_result = Column(String)
    created_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Message model representing individual messages in a conversation."""

    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    state = Column(String)
    evaluation_result = Column(String)
    matched_knowledge_components = Column(
        Text
    )  # JSON string of matched knowledge component names
    next_concept = Column(String)  # Next concept used for prompting question
    audio_data = Column(LargeBinary)
    audio_mime_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
