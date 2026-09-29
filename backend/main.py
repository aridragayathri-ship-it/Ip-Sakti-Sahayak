import os
from typing import List

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import pdf_search
import llm

from database import get_db, init_db
import models  # noqa: F401
import database as db_helpers
from schemas import (
    AskRequest,
    ClassificationRequest,
    UserCreateRequest,
    UserResponse,
    AskResponse,
    ClassificationResponse,
    HistoryItem,
)


# ================================================================
# APP
# ================================================================

app = FastAPI(
    title="IP-SAKTI Backend",
    description="Backend for the IP-SAKTI Ayurveda IP & regulatory assistant.",
    version="0.3.0",
)


# ================================================================
# DATABASE
# ================================================================

try:
    init_db()
    print("[main] Database ready (backend/ipsakti.db).")
except SQLAlchemyError as db_init_err:
    print(f"[main] WARNING: could not initialize database: {db_init_err}")


# ================================================================
# CORS
# ================================================================

DEFAULT_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]

extra_origins = os.getenv("CORS_ORIGINS", "")
allowed_origins = DEFAULT_ORIGINS + [
    origin.strip()
    for origin in extra_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================================================
# HEALTH
# ================================================================

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "pdf_pages_loaded": len(pdf_search._PAGES_CACHE),
        "ai_available": llm.has_valid_key(),
    }


# ================================================================
# PDF RELOAD
# ================================================================

@app.post("/api/reload-documents")
def reload_documents():
    """
    Reload PDFs after new documents are added.

    Useful during development. The Render service normally reloads
    them automatically whenever the application restarts.
    """
    try:
        count = pdf_search.reload_documents()
        return {
            "status": "ok",
            "pdf_pages_loaded": count,
        }
    except Exception as reload_err:
        print(f"[main] PDF reload failed: {reload_err}")
        raise HTTPException(
            status_code=500,
            detail="Could not reload the PDF documents.",
        )


# ================================================================
# USERS
# ================================================================

@app.post(
    "/api/users",
    response_model=UserResponse,
    status_code=201,
)
def create_user_endpoint(
    request: UserCreateRequest,
    db: Session = Depends(get_db),
):
    existing = db_helpers.find_user_by_email(db, request.email)

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists.",
        )

    try:
        user = db_helpers.create_user(
            db,
            request.name,
            request.email,
            request.password,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists.",
        )
    except SQLAlchemyError as err:
        db.rollback()
        print(f"[main] create_user failed: {err}")
        raise HTTPException(
            status_code=500,
            detail="Could not create user due to a database error.",
        )

    return user


# ================================================================
# ASK IP-SAKTI
# ================================================================

def _calculate_confidence(evidence: list[dict]) -> str:
    """
    Retrieval-support indicator.

    This is NOT legal certainty. It only describes how much relevant
    PDF material was retrieved for the question.
    """
    if len(evidence) >= 3:
        return "High"

    if len(evidence) >= 1:
        return "Medium"

    return "Low"


@app.post("/api/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    db: Session = Depends(get_db),
):
    """
    Answer the user's exact question using the relevant PDF evidence.

    Flow:
        Question
          -> PDF retrieval
          -> relevant passages
          -> LLM answers the actual question
          -> answer + citations + evidence saved to SQLite
    """
    question_text = request.question.strip()
    jurisdiction = (request.jurisdiction or "India").strip()

    if not question_text:
        raise HTTPException(
            status_code=400,
            detail="Question must not be empty.",
        )

    user = db_helpers.get_user_by_id(db, request.user_id)

    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"No user found with id {request.user_id}.",
        )

    # ------------------------------------------------------------
    # 1. Retrieve the most relevant PDF passages.
    # ------------------------------------------------------------
    try:
        evidence = pdf_search.search_documents(
            question_text,
            max_results=8,
        )
    except Exception as search_err:
        print(f"[main] search_documents failed: {search_err}")
        evidence = []

    # ------------------------------------------------------------
    # 2. Ask the LLM to answer THIS question from those passages.
    # ------------------------------------------------------------
    try:
        llm_result = llm.generate_answer(
            question_text,
            evidence,
            jurisdiction,
        )
    except Exception as llm_err:
        print(f"[main] generate_answer failed: {llm_err}")
        llm_result = {
            "answer": (
                "The AI service could not generate an answer. "
                "Please try again."
            ),
            "mode": "Demo Mode",
        }

    answer_text = llm_result.get(
        "answer",
        "The AI service did not return an answer.",
    )

    mode = llm_result.get("mode", "Demo Mode")
    confidence = _calculate_confidence(evidence)

    # ------------------------------------------------------------
    # 3. Save question, answer, and evidence.
    # ------------------------------------------------------------
    try:
        question_record = db_helpers.save_question(
            db,
            user.id,
            question_text,
            jurisdiction,
        )
    except SQLAlchemyError as err:
        db.rollback()
        print(f"[main] save_question failed: {err}")
        question_record = None

    if question_record is not None:
        try:
            answer_record = db_helpers.save_answer(
                db,
                question_record.id,
                answer_text,
                confidence,
            )
        except SQLAlchemyError as err:
            db.rollback()
            print(f"[main] save_answer failed: {err}")
            answer_record = None

        if answer_record is not None:
            for item in evidence:
                try:
                    db_helpers.save_evidence(
                        db,
                        answer_id=answer_record.id,
                        document_name=item.get(
                            "document",
                            "Unknown document",
                        ),
                        section=item.get("section"),
                        page=item.get("page"),
                        excerpt=item.get("excerpt"),
                        source_url=item.get("source_url"),
                    )
                except SQLAlchemyError as err:
                    db.rollback()
                    print(
                        "[main] save_evidence failed for one item: "
                        f"{err}"
                    )
                    continue

    return {
        "answer": answer_text,
        "confidence": confidence,
        "mode": mode,
        "evidence": evidence,
    }


# ================================================================
# PRODUCT CLASSIFICATION
# ================================================================
# This endpoint remains rule-based, as in the original project.
# The changes above specifically improve /api/ask.
# ================================================================

CLASSIFICATION_RULES = {
    "classical formulation": {
        "category": "Classical Ayurvedic Formulation",
        "ip_considerations": [
            "Patent",
            "Traditional Knowledge",
            "Trademark",
        ],
        "regulatory_considerations": [
            "Applicable Ayurvedic regulatory requirements",
        ],
    },
    "proprietary medicine": {
        "category": "Proprietary Ayurvedic Medicine",
        "ip_considerations": [
            "Patent",
            "Trademark",
            "Trade Secret",
        ],
        "regulatory_considerations": [
            "Applicable Ayurvedic regulatory requirements",
        ],
    },
    "new/non-classical drug": {
        "category": "New / Non-Classical Ayurvedic Drug",
        "ip_considerations": [
            "Patent",
            "Trade Secret",
            "Trademark",
        ],
        "regulatory_considerations": [
            "Applicable Ayurvedic regulatory requirements",
            "Safety and efficacy documentation",
        ],
    },
    "phytopharmaceutical": {
        "category": "Phytopharmaceutical",
        "ip_considerations": [
            "Patent",
            "Trade Secret",
        ],
        "regulatory_considerations": [
            "Phytopharmaceutical drug regulatory pathway",
        ],
    },
    "ayurveda-aahar/nutraceutical": {
        "category": "Ayurveda-Aahar / Nutraceutical",
        "ip_considerations": [
            "Trademark",
            "Trade Secret",
        ],
        "regulatory_considerations": [
            "Food / nutraceutical regulatory requirements",
        ],
    },
    "cosmetic": {
        "category": "Ayurvedic Cosmetic",
        "ip_considerations": [
            "Trademark",
            "Design",
        ],
        "regulatory_considerations": [
            "Cosmetic regulatory requirements",
        ],
    },
}

PRODUCT_TYPE_ALIASES = {
    "new formulation": "new/non-classical drug",
    "herbal food": "ayurveda-aahar/nutraceutical",
}


def _classify_confidence(
    traditional_knowledge: str,
    biological_resources: str,
) -> str:
    answers = [
        traditional_knowledge.strip().lower(),
        biological_resources.strip().lower(),
    ]

    unsure_count = sum(
        1
        for answer in answers
        if answer == "not sure"
    )

    if unsure_count == 0:
        return "High"

    if unsure_count == 1:
        return "Medium"

    return "Low"


@app.post(
    "/api/classify",
    response_model=ClassificationResponse,
)
def classify(
    request: ClassificationRequest,
    db: Session = Depends(get_db),
):
    user = db_helpers.get_user_by_id(
        db,
        request.user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"No user found with id {request.user_id}.",
        )

    raw_type = (
        request.product_type or ""
    ).strip().lower()

    if not raw_type:
        raise HTTPException(
            status_code=400,
            detail="product_type must not be empty.",
        )

    lookup_key = PRODUCT_TYPE_ALIASES.get(
        raw_type,
        raw_type,
    )

    rule = CLASSIFICATION_RULES.get(lookup_key)

    if rule is None:
        category = "Unclassified / Needs Manual Review"
        ip_considerations = [
            "Manual review recommended",
        ]
        regulatory_considerations = [
            "Manual review recommended",
        ]
        confidence = "Low"
    else:
        category = rule["category"]
        ip_considerations = list(
            rule["ip_considerations"]
        )
        regulatory_considerations = list(
            rule["regulatory_considerations"]
        )

        if (
            request.traditional_knowledge or ""
        ).strip().lower() == "yes":
            if "Traditional Knowledge" not in ip_considerations:
                ip_considerations.append(
                    "Traditional Knowledge"
                )

        if (
            request.biological_resources or ""
        ).strip().lower() in ("yes", "not sure"):
            regulatory_considerations.append(
                "Biological Diversity Act access/approval check"
            )

        if (
            request.target_market or ""
        ).strip().lower() in ("international", "both"):
            regulatory_considerations.append(
                "Destination-market regulatory classification "
                "may differ from India"
            )

        confidence = _classify_confidence(
            request.traditional_knowledge or "",
            request.biological_resources or "",
        )

    try:
        db_helpers.save_classification(
            db,
            user_id=user.id,
            product_type=request.product_type,
            traditional_knowledge=request.traditional_knowledge,
            biological_resources=request.biological_resources,
            target_market=request.target_market,
            category=category,
            confidence=confidence,
        )
    except SQLAlchemyError as err:
        db.rollback()
        print(
            f"[main] save_classification failed: {err}"
        )

    return {
        "category": category,
        "ip_considerations": ip_considerations,
        "regulatory_considerations": regulatory_considerations,
        "confidence": confidence,
    }


# ================================================================
# HISTORY
# ================================================================

@app.get(
    "/api/history/{user_id}",
    response_model=List[HistoryItem],
)
def get_history(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = db_helpers.get_user_by_id(
        db,
        user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"No user found with id {user_id}.",
        )

    try:
        questions = db_helpers.get_user_history(
            db,
            user_id,
        )
    except SQLAlchemyError as err:
        print(
            f"[main] get_user_history failed: {err}"
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not load history due to "
                "a database error."
            ),
        )

    history = []

    for question in questions:
        answer_obj = question.answer

        history.append(
            {
                "question_id": question.id,
                "question": question.question,
                "jurisdiction": question.jurisdiction,
                "answer": (
                    answer_obj.answer
                    if answer_obj
                    else None
                ),
                "confidence": (
                    answer_obj.confidence
                    if answer_obj
                    else None
                ),
                "created_at": question.created_at,
            }
        )

    return history


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
