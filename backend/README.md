# IP-SAKTI Backend

A small FastAPI backend for the IP-SAKTI prototype. It reads PDFs from
`../documents/`, does simple keyword search over them, optionally asks
OpenAI to answer questions grounded in that evidence, and now saves
every question, answer, evidence item and classification to a local
SQLite database.

No JWT, no OAuth, no PostgreSQL, no vector database, no embeddings, no
agents — deliberately simple. The frontend still handles its own
login/signup with `localStorage`; the database added here is a
separate, minimal user table used only to link questions and
classifications to a `user_id` and build a history.

## 1. Open a terminal

```bash
cd backend
```

## 2. Create a virtual environment

```bash
python -m venv venv
```

## 3. Activate it

**Windows:**
```bash
venv\Scripts\activate
```

**Mac / Linux:**
```bash
source venv/bin/activate
```

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

## 5. Set up your OpenAI key

Open `.env` and replace the placeholder:

```
OPENAI_API_KEY=your_api_key_here
```

Leave it as the placeholder and the backend still runs — `/api/ask`
just responds in **Demo Mode** instead of calling OpenAI live.

## 6. Add your source PDFs

Put PDF files (Acts, guidelines, etc.) into `../documents/`. Every
`.pdf` file there is read automatically on startup — nothing to
register.

## 7. Run the server

```bash
uvicorn main:app --reload
```

The database file `ipsakti.db` is created automatically inside
`backend/` the first time the app starts. **No separate database
installation is needed** — SQLite ships with Python.

## 8. Test it

**Health check:**
```
http://127.0.0.1:8000/api/health
```
Expected:
```json
{ "status": "ok" }
```

**Interactive testing (recommended):** open
```
http://127.0.0.1:8000/docs
```
This is Swagger UI — you can try every endpoint below directly in
the browser, no extra tools needed.

---

## Testing the full flow

1. **Create a user** — `POST /api/users`
   ```json
   { "name": "Test User", "email": "test@example.com", "password": "password123" }
   ```
   Copy the `id` from the response (e.g. `1`).

2. **Ask a question** — `POST /api/ask`, using that id as `user_id`:
   ```json
   { "question": "Can I patent a traditional Ayurvedic formulation?", "jurisdiction": "India", "user_id": 1 }
   ```

3. **Classify a product** — `POST /api/classify`, same `user_id`:
   ```json
   { "user_id": 1, "product_type": "Classical formulation", "traditional_knowledge": "Yes", "biological_resources": "Yes", "target_market": "India" }
   ```

4. **View history** — `GET /api/history/1`
   Returns every question that user has asked, most recent first.

---

## API reference

### `GET /api/health`
```json
{ "status": "ok" }
```

### `POST /api/users`
**Request**
```json
{ "name": "Test User", "email": "test@example.com", "password": "password123" }
```
**Response** (`201 Created`)
```json
{ "id": 1, "name": "Test User", "email": "test@example.com" }
```
The password is hashed with bcrypt before it's stored — it's never
returned in any response, and the raw password is never saved.
Duplicate email → `409 Conflict`.

### `POST /api/ask`
**Request**
```json
{ "question": "Can I patent a traditional Ayurvedic formulation?", "jurisdiction": "India", "user_id": 1 }
```
**Response**
```json
{
  "answer": "...",
  "confidence": "High",
  "mode": "Live",
  "evidence": [
    { "document": "Patents_Act_1970.pdf", "page": 12, "excerpt": "...", "source": "Prototype Knowledge Base" }
  ]
}
```
`mode` is `"Live"` with a real OpenAI key configured and a successful
call, `"Demo Mode"` otherwise. `confidence` reflects how much matching
evidence was found — not legal certainty. An unknown `user_id` returns
`404`. The question, generated answer, and every evidence item are
saved to SQLite regardless of Live/Demo Mode — including the
"Insufficient evidence in the current knowledge base." case.

### `POST /api/classify`
**Request**
```json
{ "user_id": 1, "product_type": "Classical formulation", "traditional_knowledge": "Yes", "biological_resources": "Yes", "target_market": "India" }
```
**Response**
```json
{
  "category": "Classical Ayurvedic Formulation",
  "ip_considerations": ["Patent", "Traditional Knowledge", "Trademark"],
  "regulatory_considerations": ["Applicable Ayurvedic regulatory requirements"],
  "confidence": "Medium"
}
```
Fully rule-based, no LLM call. The result is saved to the
`classifications` table linked to `user_id`.

### `GET /api/history/{user_id}`
```json
[
  {
    "question_id": 1,
    "question": "Can I patent a traditional Ayurvedic formulation?",
    "jurisdiction": "India",
    "answer": "...",
    "confidence": "High",
    "created_at": "2026-01-01T12:00:00"
  }
]
```
Returns `[]` if the user has no history yet. Returns `404` if
`user_id` doesn't exist. Never includes password data — the users
table isn't touched by this endpoint beyond checking the id exists.

---

## Database structure

```
User
 |-- Questions
 |     `-- Answer
 |           `-- Evidence
 |
 `-- Classifications
```

- `users` — id, name, email (unique), password (bcrypt hash), created_at
- `questions` — id, user_id (FK), question, jurisdiction, created_at
- `answers` — id, question_id (FK), answer, confidence, created_at
- `evidence` — id, answer_id (FK), document_name, section, page, excerpt, source_url
- `classifications` — id, user_id (FK), product_type, traditional_knowledge, biological_resources, target_market, category, confidence, created_at

Deleting a user cascades down through their questions → answers →
evidence, and through their classifications, so no orphaned rows are
left behind.

**Files:**
- `database.py` — engine, session, `Base`, `get_db()`, password hashing, and simple CRUD helper functions (`create_user`, `find_user_by_email`, `save_question`, `save_answer`, `save_evidence`, `save_classification`, `get_user_history`, etc.)
- `models.py` — the SQLAlchemy table definitions and relationships above
- `schemas.py` — Pydantic request/response models (kept separate from the DB models so a password hash can never accidentally leak into a response)

## Connecting the existing frontend

The frontend's Ask IP-SAKTI and Product Classification views already
call this backend (see `frontend/app.js`). One thing to know: `/api/ask`
and `/api/classify` now require a `user_id`, but the frontend's
localStorage-based login doesn't currently create or track a numeric
backend user id — that wiring hasn't been built yet. Until it is, calls
from the current frontend without a `user_id` will fail Pydantic
validation (`422`). To test the database-backed endpoints today, use
`/docs` or `curl`/Postman with a `user_id` from `POST /api/users`, as
shown in "Testing the full flow" above.

## Troubleshooting

- **`422` on `/api/ask` or `/api/classify`** — `user_id` is required
  and must be an existing user's id. Create one via `POST /api/users` first.
- **`404 No user found with id ...`** — the `user_id` you sent doesn't
  exist in the `users` table yet.
- **"Insufficient evidence" for everything** — check that PDFs exist
  in `../documents/` and the startup log shows `Loaded N page(s)...`.
- **Answers always say "Demo Mode"** — `.env` still has the placeholder
  key, or the real key is invalid/out of quota.
- **`ModuleNotFoundError` for bcrypt/passlib on a fresh install** — make
  sure you installed from `requirements.txt` as-is; it pins a specific
  `bcrypt` version that's known to work with `passlib`.
- **Want a clean slate?** — stop the server and delete `backend/ipsakti.db`.
  It will be recreated empty next time you run `uvicorn main:app --reload`.
