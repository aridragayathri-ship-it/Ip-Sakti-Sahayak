import os
from dotenv import load_dotenv

# Load backend/.env
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

_PLACEHOLDER_VALUES = {
    "",
    "your_api_key_here",
    "your-openai-api-key",
}


def has_valid_key() -> bool:
    """Return True when a usable-looking OpenAI key is configured."""
    return bool(
        OPENAI_API_KEY
        and OPENAI_API_KEY not in _PLACEHOLDER_VALUES
    )


_client = None

if has_valid_key():
    try:
        from openai import OpenAI

        _client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as init_err:
        print(f"[llm] Could not initialize OpenAI client: {init_err}")
        _client = None


# ================================================================
# IMPORTANT BEHAVIOUR
# ================================================================
# The model is grounded in the supplied PDF excerpts, but it is NOT
# forced into one fixed answer template.
#
# It should:
#   1. Understand what the user actually asked.
#   2. Answer that specific question.
#   3. Use the supplied PDFs as the factual/legal source.
#   4. Explain conditions/exceptions when the PDFs contain them.
#   5. Say what is missing when the PDFs do not support a conclusion.
#   6. Cite the document and page for important claims.
#
# This makes "What is X?", "Can I do X?", "What are the steps?",
# "What is the difference?", and "Why?" produce different answers.
# ================================================================

SYSTEM_PROMPT = """
You are IP-SAKTI, an evidence-grounded assistant for Indian intellectual
property, Ayurveda, traditional knowledge, and regulatory information.

Your job is to answer the user's ACTUAL QUESTION using the supplied PDF
evidence. Do not use a fixed response template. The shape of your answer
must follow the question.

SOURCE RULES
- Treat the supplied PDF evidence as the primary source for factual,
  legal, regulatory, procedural, and technical claims.
- Do not invent sections, rules, requirements, dates, authorities,
  exceptions, eligibility conditions, or citations.
- Do not claim that something is permitted, prohibited, patentable,
  approved, rejected, mandatory, or exempt unless the supplied evidence
  supports that statement.
- If the evidence only partially answers the question, answer the part
  that is supported and clearly identify what the PDFs do not establish.
- If the evidence does not meaningfully answer the question, say:
  "The provided PDFs do not contain enough information to answer this
  question reliably."
  Then briefly explain what information is missing, if that is clear.

QUESTION-SPECIFIC ANSWERING
- Definition question: give the definition and relevant details from
  the PDFs.
- "Can I / Is it possible" question: explain the conditions, limitations,
  exceptions, and relevant rules found in the PDFs.
- "How do I" question: provide the supported steps or process in order.
- Comparison question: compare the requested concepts directly.
- "Why" question: explain the reasons or conditions supported by the PDFs.
- List question: provide the relevant list from the PDFs.
- Scenario question: apply only the rules/evidence that actually match
  the scenario and state any uncertainty.
- Follow-up question: focus on the new question and do not repeat a
  generic introduction.

CITATIONS
For important claims, cite the source in this simple form:
[Document: filename, Page: N]

Use only document/page information supplied with the evidence.

STYLE
- Be clear, natural, and specific.
- Start with the direct answer instead of a generic introduction.
- Use headings or bullets only when they improve readability.
- Do not repeat the same paragraph structure for every question.
- Do not mention "the AI", "the prompt", or internal retrieval mechanics.
- Do not say "current knowledge base" unless discussing a limitation.
- Do not guarantee legal, patent, or regulatory outcomes.
- This is informational assistance, not a substitute for professional
  legal or regulatory advice.
"""


def _format_evidence(evidence: list[dict]) -> str:
    """Format retrieved PDF evidence with traceable document/page labels."""
    if not evidence:
        return "NO PDF EVIDENCE WAS RETRIEVED."

    blocks = []

    for number, item in enumerate(evidence, start=1):
        blocks.append(
            f"EVIDENCE {number}\n"
            f"Document: {item.get('document', 'Unknown document')}\n"
            f"Page: {item.get('page', 'Unknown page')}\n"
            f"Source: {item.get('source', 'PDF Knowledge Base')}\n"
            f"Excerpt:\n{item.get('excerpt', '')}"
        )

    return "\n\n".join(blocks)


def generate_answer(
    question: str,
    evidence: list[dict],
    jurisdiction: str = "India",
) -> dict:
    """
    Generate a natural answer grounded in the retrieved PDF evidence.

    Returns:
        {"answer": "...", "mode": "Live"}
    or
        {"answer": "...", "mode": "Demo Mode"}
    """
    if not has_valid_key() or _client is None:
        return {
            "answer": (
                "Live AI answering is unavailable because a valid OpenAI "
                "API key is not configured."
            ),
            "mode": "Demo Mode",
        }

    if not evidence:
        return {
            "answer": (
                "The provided PDFs do not contain enough information to "
                "answer this question reliably."
            ),
            "mode": "Live",
        }

    user_message = f"""
JURISDICTION:
{jurisdiction}

USER QUESTION:
{question}

PDF EVIDENCE:
{_format_evidence(evidence)}

TASK:
Answer the user's question directly and naturally.

Use the evidence above as the source for factual claims. Select only the
parts of the evidence that are relevant to this question. Do not simply
summarize every retrieved page.

If several PDF passages are relevant, combine them into one coherent
answer. If they describe conditions or exceptions, include those when
they matter to the question.

If the evidence does not support a requested conclusion, explicitly say
that the PDFs do not establish it rather than guessing.

Cite important factual claims with [Document: ..., Page: ...].
"""

    try:
        response = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.45,
            max_tokens=900,
        )

        answer_text = (
            response.choices[0].message.content or ""
        ).strip()

        if not answer_text:
            raise RuntimeError("OpenAI returned an empty answer.")

        return {
            "answer": answer_text,
            "mode": "Live",
        }

    except Exception as api_err:
        print(f"[llm] OpenAI call failed: {api_err}")

        # Keep the failure explicit instead of pretending that the model
        # answered the question.
        return {
            "answer": (
                "Live AI analysis could not be completed. The relevant "
                "PDF evidence was retrieved successfully, but the AI "
                "service returned an error."
            ),
            "mode": "Demo Mode",
        }
