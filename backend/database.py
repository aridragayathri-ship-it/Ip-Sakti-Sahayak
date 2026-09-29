
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext

# ==================================================================
# Engine / session / base
# ==================================================================
# The database file lives next to this file, inside backend/.
SQLALCHEMY_DATABASE_URL = "sqlite:///./ipsakti.db"

# check_same_thread=False is needed because SQLite by default only
# allows the thread that created a connection to use it, but FastAPI
# may handle a request on a different thread than it was opened on.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a database session and always
    closes it afterwards, even if the request raised an error.

    Usage in an endpoint:
        def some_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create every table defined on Base (users, questions, answers,
    evidence, classifications) if it doesn't already exist.

    Safe to call every time the app starts — create_all() only
    creates tables that are missing, it never drops or overwrites
    existing data.

    Must be called AFTER models.py has been imported at least once,
    so that all the model classes have registered themselves on
    Base.metadata.
    """
    Base.metadata.create_all(bind=engine)


# ==================================================================
# Password hashing
# ==================================================================
# bcrypt via passlib. Never store plain-text passwords.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Turn a plain-text password into a secure bcrypt hash."""
    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a plain-text password against a stored bcrypt hash."""
    try:
        return _pwd_context.verify(password, hashed_password)
    except Exception:
        # A malformed/unrecognized hash should fail verification,
        # not crash the request.
        return False


# ==================================================================
# CRUD helper functions
# ==================================================================
# Imported lazily inside each function (not at module load time) to
# avoid a circular import: models.py imports Base from this file, so
# this file can't import models.py at the top level.

def create_user(db: Session, name: str, email: str, password: str):
    """Create a new user with a hashed password and save it."""
    from models import User

    user = User(
        name=name,
        email=email,
        password=hash_password(password),
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def find_user_by_email(db: Session, email: str):
    """Look up a user by email, or None if no such user exists."""
    from models import User

    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int):
    """Look up a user by primary key, or None if no such user exists."""
    from models import User

    return db.query(User).filter(User.id == user_id).first()


def save_question(db: Session, user_id: int, question: str, jurisdiction: Optional[str]):
    """Save a user's question and return the saved row."""
    from models import Question

    q = Question(
        user_id=user_id,
        question=question,
        jurisdiction=jurisdiction,
        created_at=datetime.utcnow(),
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


def save_answer(db: Session, question_id: int, answer: str, confidence: str):
    """Save the generated answer for a question and return the saved row."""
    from models import Answer

    a = Answer(
        question_id=question_id,
        answer=answer,
        confidence=confidence,
        created_at=datetime.utcnow(),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def save_evidence(
    db: Session,
    answer_id: int,
    document_name: str,
    section: Optional[str],
    page: Optional[int],
    excerpt: Optional[str],
    source_url: Optional[str],
):
    """Save one evidence row linked to an answer and return the saved row."""
    from models import Evidence

    e = Evidence(
        answer_id=answer_id,
        document_name=document_name,
        section=section,
        page=page,
        excerpt=excerpt,
        source_url=source_url,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def save_classification(
    db: Session,
    user_id: int,
    product_type: str,
    traditional_knowledge: str,
    biological_resources: str,
    target_market: str,
    category: str,
    confidence: str,
):
    """Save a product classification result and return the saved row."""
    from models import Classification

    c = Classification(
        user_id=user_id,
        product_type=product_type,
        traditional_knowledge=traditional_knowledge,
        biological_resources=biological_resources,
        target_market=target_market,
        category=category,
        confidence=confidence,
        created_at=datetime.utcnow(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def get_user_history(db: Session, user_id: int):
    """
    Return every question a user has asked, most recent first.
    Each Question object has a `.answer` relationship (which in turn
    has `.evidence`), so callers can read the full thread from here.
    """
    from models import Question

    return (
        db.query(Question)
        .filter(Question.user_id == user_id)
        .order_by(Question.created_at.desc())
        .all()
    )
