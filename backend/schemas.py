"""
schemas.py
----------
Pydantic models for request validation and response shaping.

These are deliberately kept separate from the SQLAlchemy models in
models.py: models.py describes database tables, schemas.py describes
the JSON that goes over the wire. Keeping them separate means we
control exactly what gets exposed (e.g. never a password hash).
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ==================================================================
# Requests
# ==================================================================
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question")
    jurisdiction: Optional[str] = Field("India", description="'India' or 'International'")
    user_id: int = Field(..., description="ID of the user asking the question")


class ClassificationRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user requesting classification")
    product_type: str
    traditional_knowledge: str  # "Yes" | "No" | "Not sure"
    biological_resources: str   # "Yes" | "No" | "Not sure"
    target_market: str          # "India" | "International" | "Both"


class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=6, description="Plain-text password; hashed before storage")


# ==================================================================
# Responses
# ==================================================================
class UserResponse(BaseModel):
    """Returned after creating a user. Never includes the password/hash."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class EvidenceResponse(BaseModel):
    """Matches the evidence shape already used by the frontend."""
    document: str
    page: Optional[int] = None
    excerpt: Optional[str] = None
    source: Optional[str] = "Prototype Knowledge Base"


class AskResponse(BaseModel):
    answer: str
    confidence: str
    mode: str
    evidence: List[EvidenceResponse]


class ClassificationResponse(BaseModel):
    category: str
    ip_considerations: List[str]
    regulatory_considerations: List[str]
    confidence: str


class HistoryItem(BaseModel):
    """One row of a user's question/answer history."""
    question_id: int
    question: str
    jurisdiction: Optional[str] = None
    answer: Optional[str] = None
    confidence: Optional[str] = None
    created_at: datetime
