# NewsDigest

A Python-based news aggregator that discovers recent articles on a given topic, extracts their content, and generates a source-linked digest in Markdown and JSON.

The project uses deterministic, extractive summarization without LLM calls. Articles are discovered from live RSS feeds and Hacker News, rather than hardcoded article URLs.

**Tech Stack:** Python 3.10+ · Requests · Feedparser · Trafilatura

## What it does

- **Article discovery:** Fetches articles from configured publisher RSS feeds (BBC, The Guardian, NPR, TechCrunch, Ars Technica and Wired) and Hacker News.
- **Deduplication:** Normalizes URLs, removes tracking parameters and filters duplicate articles using title similarity.
- **Date filtering:** Keeps articles within the requested lookback period.
- **Content extraction:** Fetches article pages and extracts their main text using Trafilatura, while checking `robots.txt` restrictions.
- **Relevance filtering:** Uses topic keywords to filter articles before and after content extraction.
- **Extractive summarization:** Scores sentences using word frequency and topic relevance, then selects up to three sentences from the original article.
- **Fallback handling:** Uses available RSS excerpts when full-text extraction fails and flags missing information.
- **Shortfall reporting:** Reports when fewer articles are found than requested instead of filling the digest with unrelated content.

## How it works

1. **Discover:** Collects article links from RSS feeds and Hacker News.
2. **Clean:** Normalizes URLs, removes duplicates and applies the date filter.
3. **Filter:** Checks whether the topic appears in article titles or excerpts.
4. **Extract:** Fetches article pages and extracts their main content.
5. **Validate:** Applies a stricter relevance check to the extracted text.
6. **Summarize:** Selects relevant sentences using a frequency-based scoring method.
7. **Export:** Generates JSON and Markdown files in the `output/` directory.

## Project structure

```text
NewsDigest/
├── main.py           # CLI entry point and pipeline orchestration
├── sources.py        # RSS and Hacker News discovery, URL cleaning
├── extractor.py      # robots.txt checks and article extraction
├── summarizer.py     # Extractive summarization
├── requirements.txt  # Project dependencies
├── README.md
└── output/           # Generated digests
```

## Setup

**Requirements:** Python 3.10 or later.

Clone the repository and navigate into the project directory.

```bash
python -m venv .venv
```

Activate the virtual environment:

**Windows PowerShell**
```powershell
# If script execution is blocked:
Set-ExecutionPolicy -Scope Process RemoteSigned

.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the program with a topic:

```bash
python main.py --topic cybersecurity
```

Customize the number of articles and lookback period:

```bash
python main.py --topic "electric vehicles" --limit 5 --days 7
```

### Command-line arguments

| Argument | Description | Default |
|---|---|---|
| `--topic` | Topic to search for (required) | — |
| `--limit` | Maximum number of articles | 5 |
| `--days` | Number of previous days to search | 7 |

## Output

Each run generates two files in the `output/` directory:

- **JSON:** Structured article data, including titles, URLs, extracted content, summaries and extraction status.
- **Markdown:** A readable digest containing article links and summaries.

The filenames follow this format:

```text
output/
├── cybersecurity_2026-11-24.json
└── cybersecurity_2026-11-24.md
```

If fewer relevant articles are available than requested, the program reports the shortfall.

## Known limitations

- **Keyword matching:** Relevance checks rely on literal topic keywords, so articles using synonyms or alternative terminology may be missed.
- **RSS coverage:** Feeds expose a limited selection of recent articles, which can affect results for niche topics.
- **Restricted pages:** Paywalls, HTTP errors and website restrictions can prevent full-text extraction.
- **Hacker News dates:** Submission timestamps may differ from the original article publication dates.
- **Extractive summaries:** Selected sentences retain their original wording, so summaries may occasionally lack smooth transitions.

## Possible improvements

- Add automated tests using saved RSS and HTML fixtures.
- Expand topic matching with synonym support.
- Improve discovery coverage with additional news sources.
- Introduce concurrent article fetching with per-domain request limits.