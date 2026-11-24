
"""Discovery: publisher RSS feeds + Hacker News API, then date filtering and de-duplication."""
import difflib
import html
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests

log = logging.getLogger(__name__)

FEEDS = {
    "BBC": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Guardian": "https://www.theguardian.com/world/rss",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Wired": "https://www.wired.com/feed/rss",
}
HN_API = "https://hn.algolia.com/api/v1/search_by_date"
HEADERS = {"User-Agent": "NewsDigest/1.0 (student project)"}


def request_url(url, params=None):
    """GET with a timeout and one retry. Returns the response, or None on failure."""
    for attempt in range(2):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return response
        except requests.HTTPError as error:
            log.warning("Request failed (%s): %s", url, error)
            if error.response is not None and error.response.status_code < 500:
                return None
        except requests.RequestException as error:
            log.warning("Request failed (%s): %s", url, error)

        if attempt == 0:
            time.sleep(1)

    return None


def clean_text(value):
    """Strip HTML tags/entities from RSS excerpts."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def relevant(text, topic, strict=False):
    """Match topic words against singular and plural forms as whole words."""
    text = text.lower()
    words = re.findall(r"\w+", topic.lower())

    def matches(word):
        variants = {word}

        if word.endswith("ies") and len(word) > 3:
            variants.add(word[:-3] + "y")
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 2:
            variants.add(word[:-1])
        else:
            variants.add(word + "s")
            if word.endswith(("s", "x", "z", "ch", "sh")):
                variants.add(word + "es")
            if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
                variants.add(word[:-1] + "ies")

        return any(re.search(rf"\b{re.escape(v)}\b", text) for v in variants)

    hits = [matches(word) for word in words]
    return all(hits) if strict else any(hits)


def normalize_url(url):
    p = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", urlencode(query), ""))


def get_date(value):
    """Parse an ISO or RFC-2822 date into a UTC ISO string, or None."""
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            return None
    return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def make_article(title, source, url, date, excerpt=""):
    return {"title": title, "source": source, "url": url, "published_at": date,
            "excerpt": excerpt, "missing_fields": [] if date else ["published_at"]}


def discover_rss(topic):
    articles = []

    for source, feed_url in FEEDS.items():
        try:
            response = request_url(feed_url)

            if response is None:
                continue

            feed = feedparser.parse(response.content)

            for item in feed.entries:
                title = (item.get("title") or "").strip()
                link = (item.get("link") or "").strip()
                excerpt = clean_text(item.get("summary"))

                if title and link and relevant(f"{title} {excerpt}", topic):
                    date = get_date(item.get("published") or item.get("updated"))
                    articles.append(make_article(title, source, link, date, excerpt))

        except Exception as error:
            log.warning("Could not process %s RSS feed: %s", source, error)

        finally:
            time.sleep(1)

    return articles


def discover_hn(topic, days):
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    params = {"query": topic, "tags": "story", "hitsPerPage": 50,
              "numericFilters": f"created_at_i>{cutoff}"}
    response = request_url(HN_API, params)
    if response is None:
        return []
    try:
        hits = response.json().get("hits", [])
    except ValueError as error:
        log.warning("Hacker News data error: %s", error)
        return []
    articles = []
    for item in hits:
        title, url = (item.get("title") or "").strip(), (item.get("url") or "").strip()
        if title and url and relevant(title, topic):
            excerpt = clean_text(item.get("story_text") or "")
            articles.append(make_article(title, urlparse(url).netloc.lower(), url,
                                         get_date(item.get("created_at")), excerpt))
    return articles



def clean_articles(articles, days):
    """Filter old articles, deduplicate, and prioritize publisher diversity."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    unique = []
    seen_urls = set()

    for article in articles:
        if article["published_at"]:
            published = datetime.fromisoformat(article["published_at"])
            if published < cutoff:
                continue

        key = normalize_url(article["url"])
        if key in seen_urls:
            continue

        seen_urls.add(key)

        if any(
            difflib.SequenceMatcher(
                None,
                article["title"].lower(),
                existing["title"].lower()
            ).ratio() > 0.85
            for existing in unique
        ):
            continue

        unique.append(article)

    unique.sort(
        key=lambda article: article["published_at"] or "",
        reverse=True
    )

    # Take the newest article from each source before taking a second.
    selected = []
    remaining = []

    seen_sources = set()

    for article in unique:
        source = article["source"].lower()

        if source not in seen_sources:
            selected.append(article)
            seen_sources.add(source)
        else:
            remaining.append(article)

    return selected + remaining

