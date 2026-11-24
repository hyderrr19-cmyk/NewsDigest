
"""Retrieval: robots.txt check, polite page fetch, main-text extraction."""
import logging
import re
import time
from functools import lru_cache
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
import trafilatura

from sources import HEADERS, request_url

log = logging.getLogger(__name__)

BOILERPLATE = (
    r"browse the .*? online",
    r"clicking the section headings",
    r"cite this report",
    r"licensed under .*",
    r"all rights reserved",
    r"privacy policy",
    r"cookie policy",
)


@lru_cache(maxsize=None)
def robots_for(origin):
    """Fetch and cache robots.txt. 4xx = no rules (allow); unreachable/5xx = disallow."""
    parser = RobotFileParser()

    try:
        response = requests.get(
            f"{origin}/robots.txt", headers=HEADERS, timeout=10
        )
    except requests.RequestException:
        parser.disallow_all = True
        return parser

    if response.ok:
        parser.parse(response.text.splitlines())
    elif response.status_code < 500:
        parser.allow_all = True
    else:
        parser.disallow_all = True

    return parser


def allowed(url):
    p = urlparse(url)
    return robots_for(f"{p.scheme}://{p.netloc}").can_fetch(
        HEADERS["User-Agent"], url
    )


def remove_boilerplate(text):
    """Remove common navigation, citation and legal boilerplate."""
    lines = text.splitlines()
    cleaned = []
    skip_citation = False

    for line in lines:
        value = line.strip()
        if not value:
            continue

        lower = value.lower()

        if skip_citation:
            skip_citation = False
            continue

        if re.search(r"cite this (report|article|page)", lower):
            skip_citation = True
            continue

        if any(re.search(pattern, lower) for pattern in BOILERPLATE):
            continue

        cleaned.append(value)

    return "\n".join(cleaned)


def extract_article(url):
    """Return meaningful article text, or None if unavailable or insufficient."""
    if not allowed(url):
        log.warning("robots.txt disallows: %s", url)
        return None

    time.sleep(1)
    response = request_url(url)

    if response is None:
        return None

    text = trafilatura.extract(
        response.text,
        favor_precision=True,
        include_comments=False,
        include_tables=False
    )

    if not text:
        log.warning("No article text extracted: %s", url)
        return None

    text = remove_boilerplate(text)

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    meaningful = [
        sentence for sentence in sentences
        if len(sentence.split()) >= 8
        and sentence.rstrip().endswith((".", "!", "?"))
    ]

    if len(meaningful) < 3:
        log.warning("Insufficient article content extracted: %s", url)
        return None

    return text
