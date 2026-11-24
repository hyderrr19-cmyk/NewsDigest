
"""Extractive summarization: select coherent original sentences without inventing facts."""
import re
from collections import Counter

STOPWORDS = set("""the a an and or but is are was were be been to of in on for with by from as at this that
it its they their he she we you our your his her i has have had will would can could do does did not no
said says also more than who what which when there about into over after before its their them these those
""".split())


def _words(text):
    return re.findall(r"\b[a-z]+\b", text.lower())


def _split_sentences(text):
    """Split article text into original sentences, including line-break boundaries."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [part.strip() for part in parts if part.strip()]


def _well_formed(sentence):
    """Reject headings, fragments, and malformed sentence candidates."""
    words = _words(sentence)

    return (
        40 <= len(sentence) <= 400
        and len(words) >= 8
        and sentence[-1] in ".!?"
        and sentence.count("“") == sentence.count("”")
        and sentence.count('"') % 2 == 0
    )


def summarize(text, topic, n=3):
    """Return a coherent group of 2–4 original sentences."""
    candidates = [
        sentence for sentence in _split_sentences(text)
        if _well_formed(sentence)
    ]

    if len(candidates) < 2:
        return ""

    n = max(2, min(n, 4, len(candidates)))

    topic_words = set(_words(topic))
    content_words = [
        word for word in _words(text)
        if word not in STOPWORDS
    ]
    frequencies = Counter(content_words)

    def sentence_score(sentence):
        words = _words(sentence)
        if not words:
            return 0

        topic_hits = sum(word in topic_words for word in words)
        frequency = sum(frequencies[word] for word in words) / len(words)

        return frequency + (topic_hits / len(words)) * 8

    def cohesion(first, second):
        first_words = set(_words(first)) - STOPWORDS
        second_words = set(_words(second)) - STOPWORDS

        if not first_words or not second_words:
            return 0

        overlap = len(first_words & second_words)
        return overlap / min(len(first_words), len(second_words))

    best_start = 0
    best_score = float("-inf")

    for start in range(len(candidates) - n + 1):
        window = candidates[start:start + n]

        relevance = sum(sentence_score(s) for s in window) / n
        connection = sum(
            cohesion(window[i], window[i + 1])
            for i in range(n - 1)
        ) / (n - 1)

        score = relevance + connection * 3

        if score > best_score:
            best_score = score
            best_start = start

    return " ".join(candidates[best_start:best_start + n])


def top_themes(summaries, topic, limit=5):
    """Most frequent non-trivial words across all summaries."""
    excluded = STOPWORDS | set(_words(topic))
    words = [
        word for word in _words(" ".join(summaries))
        if len(word) > 3 and word not in excluded
    ]
    return [word for word, _ in Counter(words).most_common(limit)]
