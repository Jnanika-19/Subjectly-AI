from __future__ import annotations

import hashlib
import re
from collections import Counter


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?i)\b(?:dr|prof|associate professor|department of|university)\b.*", "", text)
    return text.strip()


def detect_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    current_title = "Overview"
    current_lines: list[str] = []
    current_page = 1
    heading_pattern = re.compile(r"^(chapter|unit|module|lesson)\b", re.IGNORECASE)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[Page "):
            current_page = int(re.findall(r"\d+", line)[0])
            continue
        looks_like_heading = (
            heading_pattern.match(line)
            or (len(line.split()) <= 8 and line == line.title())
            or (len(line.split()) <= 8 and line.isupper())
        )
        if looks_like_heading and current_lines:
            body = " ".join(current_lines).strip()
            if body:
                sections.append(
                    {
                        "title": current_title,
                        "content": body,
                        "chapter": current_title if "chapter" in current_title.lower() else "",
                        "unit": current_title if "unit" in current_title.lower() else "",
                        "page": current_page,
                    }
                )
            current_title = line
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append(
            {
                "title": current_title,
                "content": " ".join(current_lines).strip(),
                "chapter": current_title if "chapter" in current_title.lower() else "",
                "unit": current_title if "unit" in current_title.lower() else "",
                "page": current_page,
            }
        )

    return sections or [{"title": "Overview", "content": clean_text(text), "chapter": "", "unit": "", "page": 1}]


def summarize_section(text: str, max_sentences: int = 2) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(text))
    return " ".join(sentences[:max_sentences]).strip()


def chunk_text(text: str, chunk_words: int, overlap: int) -> list[str]:
    normalized = clean_text(text)
    if not normalized:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current_parts: list[str] = []
    current_words = 0
    min_words = max(240, chunk_words - 80)

    for paragraph in paragraphs:
        words = paragraph.split()
        paragraph_len = len(words)
        if paragraph_len > chunk_words + 80:
            sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", paragraph) if item.strip()]
            for sentence in sentences:
                sentence_words = len(sentence.split())
                if current_parts and current_words + sentence_words > chunk_words:
                    chunks.append(" ".join(current_parts).strip())
                    tail_words = " ".join(" ".join(current_parts).split()[-overlap:]).strip()
                    current_parts = [tail_words] if tail_words else []
                    current_words = len(tail_words.split())
                current_parts.append(sentence)
                current_words += sentence_words
            continue

        if current_parts and current_words + paragraph_len > chunk_words and current_words >= min_words:
            chunks.append(" ".join(current_parts).strip())
            tail_words = " ".join(" ".join(current_parts).split()[-overlap:]).strip()
            current_parts = [tail_words] if tail_words else []
            current_words = len(tail_words.split())

        current_parts.append(paragraph)
        current_words += paragraph_len

    if current_parts:
        chunks.append(" ".join(current_parts).strip())

    cleaned_chunks = []
    seen = set()
    for chunk in chunks:
        normalized_chunk = re.sub(r"\s+", " ", chunk).strip()
        if normalized_chunk and normalized_chunk not in seen:
            seen.add(normalized_chunk)
            cleaned_chunks.append(normalized_chunk)
    return cleaned_chunks


def keyword_signature(text: str, limit: int = 6) -> list[str]:
    tokens = tokenize_for_search(text)
    counts = Counter(token for token in tokens if token not in stop)
    return [word for word, _ in counts.most_common(limit)]


def stable_hash(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)


stop = {
    "the", "and", "for", "that", "with", "from", "this", "have", "into",
    "their", "there", "will", "your", "about", "which", "using", "used",
    "what", "when", "where", "while", "then", "been", "them", "they",
    "were", "also", "than", "such", "more", "most", "very", "each",
    "page", "pages", "note", "notes", "subject", "explain", "tell", "give",
}


def tokenize_for_search(text: str) -> list[str]:
    return [
        token for token in re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", text.lower())
        if token not in stop
    ]


def keyword_overlap_score(query: str, text: str) -> float:
    query_tokens = set(tokenize_for_search(query))
    if not query_tokens:
        return 0.0
    text_tokens = set(tokenize_for_search(text))
    if not text_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / len(query_tokens)


def clean_answer_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned: list[str] = []
    skip_patterns = (
        r"^source\s+\d+",
        r"^sources used:",
        r"^document:",
        r"^page:\s*\d+",
        r"^(dr|prof|associate professor)\b",
    )
    for line in lines:
        if not line:
            if cleaned and cleaned[-1]:
                cleaned.append("")
            continue
        if any(re.match(pattern, line, flags=re.IGNORECASE) for pattern in skip_patterns):
            continue
        if len(line.split()) <= 2 and not re.match(r"^(Definition|Key Points|Example)\b", line, flags=re.IGNORECASE):
            continue
        cleaned.append(re.sub(r"\s+", " ", line))
    result = "\n".join(cleaned).strip()
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result
