import os
import re
from collections import Counter

import pymupdf


# ================================================================
# PDF KNOWLEDGE-BASE SEARCH
# ================================================================
# This module reads every PDF inside ../documents/ and searches the
# extracted text. It is intentionally dependency-light: no vector
# database or embedding package is required.
#
# The important difference from the old version is that retrieval
# now considers:
#   - important words from the question
#   - phrase matches
#   - related word forms
#   - how much of the question is covered
#   - matches in titles/headings
#
# It also sends a much larger, better-focused excerpt to the LLM.
# ================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.normpath(
    os.path.join(BASE_DIR, "..", "documents")
)

MAX_EXCERPT_LENGTH = 1800


STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "be", "been", "being",
    "and", "or", "but", "if", "then", "else",
    "for", "to", "of", "in", "on", "at", "by",
    "with", "about", "into", "through", "during",
    "can", "could", "should", "would", "will",
    "shall", "may", "might",
    "do", "does", "did",
    "has", "have", "had",
    "i", "you", "he", "she", "it", "we", "they",
    "this", "that", "these", "those",
    "as", "not", "no", "yes",
    "my", "your", "his", "her", "its", "our", "their",
    "what", "which", "who", "whom", "how",
    "why", "when", "where",
    "please", "tell", "explain", "give", "information",
    "regarding", "related", "possible"
}


def _normalise_text(text: str) -> str:
    """Normalise whitespace while preserving readable PDF text."""
    return " ".join((text or "").split())


def _extract_words(text: str) -> list[str]:
    """
    Extract useful lowercase words.

    Keeps reasonably long words because IP/legal documents often contain
    terms such as 'patentability', 'traditional', 'biodiversity',
    'formulation', and 'regulatory'.
    """
    text = (text or "").lower()
    words = re.findall(r"[a-z][a-z0-9\-]{2,}", text)

    cleaned = []
    for word in words:
        word = word.strip("-")
        if len(word) < 3 or word in STOPWORDS:
            continue
        cleaned.append(word)

    return cleaned


def _word_variants(word: str) -> set[str]:
    """
    Generate a few safe lexical variants.

    This is not a full linguistic stemmer. It simply helps a question
    containing 'patenting' find text containing 'patent', etc.
    """
    word = word.lower().strip()
    variants = {word}

    suffixes = (
        "ingly", "edly", "ation", "tions", "ments", "ment",
        "ings", "ing", "ed", "es", "s"
    )

    for suffix in suffixes:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            root = word[:-len(suffix)]
            variants.add(root)
            if len(root) > 4:
                variants.add(root + "e")
            break

    return variants


def _expand_keywords(question: str) -> list[str]:
    """
    Create a compact list of useful query terms plus simple variants.
    """
    original_words = _extract_words(question)

    expanded = []
    seen = set()

    for word in original_words:
        for variant in _word_variants(word):
            if variant and variant not in seen:
                expanded.append(variant)
                seen.add(variant)

    return expanded


def _query_phrases(question: str) -> list[str]:
    """
    Extract 2-4 word phrases from the question.

    Phrase matches are given extra weight because they usually represent
    the user's actual topic better than isolated common words.
    """
    words = _extract_words(question)

    phrases = []
    for size in (4, 3, 2):
        if len(words) < size:
            continue

        for i in range(len(words) - size + 1):
            phrase = " ".join(words[i:i + size])
            if phrase not in phrases:
                phrases.append(phrase)

    return phrases[:12]


def load_documents() -> list[dict]:
    """
    Read every PDF from ../documents/ page by page.

    Each page is kept separately so the final answer can cite the
    exact document and page that supplied the evidence.
    """
    pages = []

    if not os.path.isdir(DOCUMENTS_DIR):
        print(
            f"[pdf_search] Documents folder not found: {DOCUMENTS_DIR}"
        )
        return pages

    filenames = sorted(
        filename
        for filename in os.listdir(DOCUMENTS_DIR)
        if filename.lower().endswith(".pdf")
    )

    if not filenames:
        print(
            f"[pdf_search] No PDF files found in {DOCUMENTS_DIR}"
        )
        return pages

    for filename in filenames:
        filepath = os.path.join(DOCUMENTS_DIR, filename)

        try:
            with pymupdf.open(filepath) as doc:
                for page_index in range(len(doc)):
                    try:
                        page_text = doc[page_index].get_text("text") or ""
                    except Exception as page_err:
                        print(
                            f"[pdf_search] Could not read page "
                            f"{page_index + 1} of {filename}: {page_err}"
                        )
                        continue

                    page_text = page_text.strip()

                    if not page_text:
                        continue

                    pages.append(
                        {
                            "document": filename,
                            "page": page_index + 1,
                            "text": page_text,
                        }
                    )

        except Exception as file_err:
            print(
                f"[pdf_search] Skipping unreadable PDF "
                f"'{filename}': {file_err}"
            )

    print(
        f"[pdf_search] Loaded {len(pages)} page(s) "
        f"from {len(filenames)} PDF file(s)."
    )

    return pages


_PAGES_CACHE = load_documents()


def reload_documents() -> int:
    """Reload all PDFs without restarting the Python process."""
    global _PAGES_CACHE
    _PAGES_CACHE = load_documents()
    return len(_PAGES_CACHE)


def _find_best_excerpt(
    page_text: str,
    keywords: list[str],
    phrases: list[str],
    max_len: int = MAX_EXCERPT_LENGTH,
) -> str:
    """
    Return a large readable passage centred on the strongest match.

    Larger excerpts are important because a legal/regulatory answer can
    depend on conditions, exceptions, definitions, or the next sentence.
    """
    clean_text = _normalise_text(page_text)
    lower_text = clean_text.lower()

    candidate_positions = []

    for phrase in phrases:
        position = lower_text.find(phrase.lower())
        if position >= 0:
            candidate_positions.append((position, len(phrase) + 100))

    for keyword in keywords:
        position = lower_text.find(keyword.lower())
        if position >= 0:
            candidate_positions.append((position, len(keyword)))

    if not candidate_positions:
        return clean_text[:max_len].rstrip() + (
            "..." if len(clean_text) > max_len else ""
        )

    # Prefer the earliest strong phrase/keyword so the excerpt begins
    # near the relevant portion of the page.
    match_position = min(candidate_positions, key=lambda item: item[0])[0]

    # Keep enough context before and after the match.
    start = max(0, match_position - max_len // 3)
    end = min(len(clean_text), start + max_len)

    if end - start < max_len:
        start = max(0, end - max_len)

    snippet = clean_text[start:end]

    if start > 0:
        snippet = "... " + snippet

    if end < len(clean_text):
        snippet = snippet.rstrip() + "..."

    return snippet


def _score_page(
    page: dict,
    original_keywords: list[str],
    expanded_keywords: list[str],
    phrases: list[str],
) -> float:
    """
    Score one page for relevance to the question.

    The score rewards coverage of different query concepts instead of
    merely counting one word many times.
    """
    text = _normalise_text(page.get("text", ""))
    lower_text = text.lower()

    if not text:
        return 0.0

    word_counter = Counter(_extract_words(text))

    # Unique original concepts found on the page.
    matched_original = 0
    frequency_score = 0.0

    for keyword in original_keywords:
        variants = _word_variants(keyword)

        best_count = 0
        for variant in variants:
            best_count = max(best_count, word_counter.get(variant, 0))

        if best_count > 0:
            matched_original += 1
            # First occurrence matters; repeated occurrences matter, but
            # much less, so one repeated term cannot dominate retrieval.
            frequency_score += min(best_count, 5) * 0.7

    coverage = (
        matched_original / len(original_keywords)
        if original_keywords
        else 0.0
    )

    phrase_score = 0.0
    for phrase in phrases:
        if phrase.lower() in lower_text:
            phrase_score += 5.0

    # Headings are often highly informative in Acts/guidelines.
    heading_score = 0.0
    first_part = lower_text[:500]
    for keyword in original_keywords:
        if keyword.lower() in first_part:
            heading_score += 0.5

    return (
        coverage * 10.0
        + frequency_score
        + phrase_score
        + heading_score
    )


def search_documents(
    question: str,
    max_results: int = 8,
) -> list[dict]:
    """
    Search all cached PDF pages and return the most relevant evidence.

    The returned structure remains compatible with the existing API:
      document, page, excerpt, source
    """
    if not question or not question.strip():
        return []

    if not _PAGES_CACHE:
        return []

    original_keywords = _extract_words(question)

    if not original_keywords:
        return []

    expanded_keywords = _expand_keywords(question)
    phrases = _query_phrases(question)

    scored_pages = []

    for page in _PAGES_CACHE:
        score = _score_page(
            page,
            original_keywords,
            expanded_keywords,
            phrases,
        )

        if score > 0:
            scored_pages.append((score, page))

    if not scored_pages:
        return []

    scored_pages.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    # Avoid returning several nearly identical pages from the same PDF
    # unless they are genuinely strong matches.
    selected = []
    document_counts = Counter()

    for score, page in scored_pages:
        document = page["document"]

        # Allow several pages from one document, but don't let it occupy
        # every result slot when other relevant PDFs exist.
        if document_counts[document] >= 3 and len(selected) < max_results - 1:
            continue

        selected.append((score, page))
        document_counts[document] += 1

        if len(selected) >= max_results:
            break

    results = []

    for score, page in selected:
        excerpt = _find_best_excerpt(
            page["text"],
            expanded_keywords,
            phrases,
        )

        results.append(
            {
                "document": page["document"],
                "page": page["page"],
                "excerpt": excerpt,
                "source": "PDF Knowledge Base",
                "relevance_score": round(score, 2),
            }
        )

    return results
