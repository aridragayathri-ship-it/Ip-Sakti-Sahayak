"""
models.py
---------
SQLAlchemy ORM models for the IP-SAKTI prototype database.

Relationship structure:

    User
     |-- Questions
     |     `-- Answer
     |           `-- Evidence
     |
     `-- Classifications

Deleting a User cascades down to their Questions and Classifications.
Deleting a Question cascades to its Answer. Deleting an Answer
cascades to its Evidence. This keeps the database tidy in a
prototype where a "delete my account" style action shouldn't leave
orphaned rows behind.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # bcrypt hash, never plain text
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship(
        "Question",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    classifications = relationship(
        "Classification",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    jurisdiction = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="questions")
    # One question -> one saved answer in this prototype.
    answer = relationship(
        "Answer",
        back_populates="question",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    answer = Column(Text, nullable=False)
    confidence = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    question = relationship("Question", back_populates="answer")
    evidence = relationship(
        "Evidence",
        back_populates="answer",
        cascade="all, delete-orphan",
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    answer_id = Column(Integer, ForeignKey("answers.id"), nullable=False)
    document_name = Column(String, nullable=False)
    section = Column(String, nullable=True)
    page = Column(Integer, nullable=True)
    excerpt = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)

    answer = relationship("Answer", back_populates="evidence")


class Classification(Base):
    __tablename__ = "classifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_type = Column(String, nullable=False)
    traditional_knowledge = Column(String, nullable=True)
    biological_resources = Column(String, nullable=True)
    target_market = Column(String, nullable=True)
    category = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="classifications")
