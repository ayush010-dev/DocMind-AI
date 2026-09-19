import re
import urllib.parse

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


# ==============================
# Geographic / Place Suffixes
# ==============================
# If a result title ends with these patterns for a non-geographic query,
# it's likely a false entity match (e.g., "Model Development, Alberta").

_GEO_PATTERNS = re.compile(
    r",\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*$|"        # ", Alberta" or ", New South Wales"
    r"\b(?:city|town|village|county|province|state|region|district|municipality)\b",
    re.IGNORECASE
)

# Words that suggest a geographic entity in titles when user asked a concept question
_GEO_TRIGGER_WORDS = {
    "alberta", "ontario", "british columbia", "quebec", "saskatchewan",
    "manitoba", "nova scotia", "new brunswick", "newfoundland", "pei",
    "new south wales", "victoria", "queensland", "western australia",
    "california", "texas", "florida", "new york", "nevada", "utah",
    "wikipedia", "county", "municipality", "borough", "township",
    "parish", "district", "ward"
}


def _is_geographic_false_match(title: str, topic: str) -> bool:
    """
    Returns True if the result title appears to refer to a geographic/place
    entity when the user's query is clearly about a concept/technology.
    Example: title="Model Development, Alberta" when topic="model development"
    """
    title_lower = title.lower()

    # If title contains geographic trigger words and the topic doesn't
    topic_lower = topic.lower()
    for word in _GEO_TRIGGER_WORDS:
        if word in title_lower and word not in topic_lower:
            # Exception: if the topic itself mentions a place, allow it
            return True

    # Comma + proper noun at end of title = place disambiguation page
    if _GEO_PATTERNS.search(title):
        # Only flag if topic is short (< 4 words) and looks like a concept
        topic_words = topic_lower.split()
        if len(topic_words) <= 4:
            return True

    return False


def _score_relevance(title: str, snippet: str, topic: str) -> float:
    """
    Compute a 0-1 overlap score between the result (title + snippet) and the
    user's actual topic. Uses simple word-overlap (Jaccard-like) weighted
    toward title matches.
    Returns a float between 0.0 and 1.0.
    """
    topic_words = set(
        re.sub(r"[^\w\s]", "", topic.lower()).split()
    ) - {"the", "a", "an", "is", "are", "was", "what", "how", "why", "explain"}

    if not topic_words:
        return 0.5  # No meaningful words → neutral

    title_words = set(re.sub(r"[^\w\s]", "", title.lower()).split())
    snippet_words = set(re.sub(r"[^\w\s]", "", snippet.lower()).split())

    title_overlap = len(topic_words & title_words) / len(topic_words)
    snippet_overlap = len(topic_words & snippet_words) / len(topic_words)

    # Title match is worth more than snippet match
    score = (title_overlap * 0.6) + (snippet_overlap * 0.4)
    return min(score, 1.0)


def filter_web_results(
    results: list[dict],
    topic: str,
    min_relevance: float = 0.15
) -> list[dict]:
    """
    Filter and rank raw web search results by:
    1. Reject geographic false matches.
    2. Score by topic word overlap with title and snippet.
    3. Keep only results above min_relevance threshold.
    4. Return sorted best-first.

    Args:
        results: Raw list of web search results.
        topic: The actual concept/entity the user is asking about.
        min_relevance: Minimum score to include a result (0–1).
    """
    scored = []
    for item in results:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        url = item.get("url", "")

        # Hard reject: geographic false matches
        if _is_geographic_false_match(title, topic):
            print(f"[WebFilter] Rejected geographic match: '{title}'")
            continue

        # Hard reject: empty title or url
        if not title.strip() or not url.strip():
            continue

        score = _score_relevance(title, snippet, topic)
        if score < min_relevance:
            print(f"[WebFilter] Rejected low-relevance ({score:.2f}): '{title}'")
            continue

        scored.append((score, item))

    # Sort best first
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


def search_web(query: str, max_results: int = 8) -> list[dict]:
    """
    Perform a web search using DuckDuckGo and return structured results.
    Fetches more candidates than needed so filter_web_results can trim to the best ones.
    Each result contains: title, url, snippet, domain.
    Returns [] on any failure or empty query.
    """
    if not query or not query.strip():
        return []

    try:
        results = []
        with DDGS() as ddgs:
            # Fetch extra candidates so the filter has room to work
            raw_results = list(ddgs.text(query.strip(), max_results=max_results))

            for item in raw_results:
                url = item.get("href") or item.get("url") or ""
                title = item.get("title") or ""
                snippet = item.get("body") or item.get("snippet") or ""

                if not url or not title:
                    continue

                parsed = urllib.parse.urlparse(url)
                domain = parsed.netloc.replace("www.", "")

                results.append({
                    "type": "web",
                    "title": title.strip(),
                    "url": url.strip(),
                    "snippet": snippet.strip(),
                    "domain": domain
                })

        return results
    except Exception as e:
        print(f"[WebSearch Warning] Web search failed for query '{query}': {e}")
        return []
