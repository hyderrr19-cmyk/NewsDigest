"""NewsDigest CLI: python main.py --topic "cybersecurity" --limit 5 --days 7"""
import argparse
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from extractor import extract_article
from sources import clean_articles, discover_hn, discover_rss, relevant
from summarizer import summarize, top_themes

log = logging.getLogger("newsdigest")


def process(article, topic):
    """Retrieve + validate + summarize one article. Returns a record, or None if it should be skipped."""
    text = extract_article(article["url"])
    full_text = bool(text)
    text = text or article["excerpt"]  # fall back to the RSS excerpt, flagged below
    if not text or not relevant(f"{article['title']} {text}", topic, strict=True):
        return None
    summary = summarize(text, topic)
    if not summary:
        return None
    return {
        **{k: article[k] for k in ("title", "source", "url", "published_at")},
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "excerpt": text,
        "excerpt_is_full_text": full_text,
        "summary": summary,
        "missing_fields": article["missing_fields"] + ([] if full_text else ["full_text"]),
    }


def write_reports(topic, results, notes):
    out = Path("output")
    out.mkdir(exist_ok=True)
    stem = f"{re.sub(r'[^a-zA-Z0-9_-]+', '_', topic).strip('_')}_{datetime.now():%Y-%m-%d}"
    report = {"topic": topic, "generated_at": datetime.now(timezone.utc).isoformat(),
              "notes": notes, "articles": results}
    (out / f"{stem}.json").write_text(json.dumps(report, indent=4, ensure_ascii=False), encoding="utf-8")

    themes = top_themes([r["summary"] for r in results], topic)
    lines = [f"# News Digest: {topic}", "", "## Top Themes", "", ", ".join(themes) or "No themes found", ""]
    for r in results:
        flag = " *(summary based on RSS excerpt only)*" if not r["excerpt_is_full_text"] else ""
        lines += [f"## {r['title']}", "",
                  f"**Source:** {r['source']}  ", f"**Published:** {r['published_at'] or 'Unknown'}", "",
                  r["summary"] + flag, "", f"[Read article]({r['url']})", ""]
    if notes:
        lines += ["## Note", "", *notes]
    (out / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out / f"{stem}.json", out / f"{stem}.md"



def run(topic, limit, days):
    print("\nNewsDigest")
    print("─" * 30)
    print(f"Topic: {topic}\n")
    print("Discovering articles...\n")

    discovered = []

    try:
        discovered.extend(discover_rss(topic))
    except Exception as error:
        log.warning("RSS discovery failed: %s", error)

    try:
        discovered.extend(discover_hn(topic, days))
    except Exception as error:
        log.warning("Hacker News discovery failed: %s", error)

    articles = clean_articles(discovered, days)

    results = []
    for article in articles:
        if len(results) >= limit:
            break
        try:
            record = process(article, topic)
        except Exception as error:
            log.warning("Skipping %s: %s", article["url"], error)
            continue

        if record:
            results.append(record)

    notes = []
    if len(results) < limit:
        notes.append(
            f"Requested {limit} articles, but only {len(results)} "
            "passed retrieval and relevance checks."
        )

    json_path, md_path = write_reports(topic, results, notes)

    print(f"{len(results)} articles processed successfully.\n")
    print("Reports saved:")
    print(f"  - {json_path}")
    print(f"  - {md_path}")

    for note in notes:
        print(f"\nNote: {note}")




if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Find recent news on a topic and summarize it."
    )
    parser.add_argument("--topic", help="news topic")
    parser.add_argument("--limit", type=int, default=5, help="max articles (default 5)")
    parser.add_argument("--days", type=int, default=7, help="look-back period (default 7)")

    args = parser.parse_args()

    topic = args.topic or input("Enter topic: ").strip()

    if not topic:
        parser.error("Topic cannot be empty.")

    if args.limit <= 0:
        parser.error("Article limit must be greater than 0.")

    if args.days <= 0:
        parser.error("Number of days must be greater than 0.")

    limit = args.limit
    days = args.days

    if "--limit" not in __import__("sys").argv:
        value = input("Number of articles: ").strip()
        if value:
            try:
                limit = int(value)
            except ValueError:
                parser.error("Article limit must be a whole number.")

    if "--days" not in __import__("sys").argv:
        value = input("Look back how many days?: ").strip()
        if value:
            try:
                days = int(value)
            except ValueError:
                parser.error("Number of days must be a whole number.")

    if limit <= 0 or days <= 0:
        parser.error("Article limit and number of days must be greater than 0.")

    run(topic, limit, days)

