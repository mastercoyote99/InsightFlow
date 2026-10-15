"""Task-local source registry and syntactic citation checks (no network)."""
import copy
import re
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url):
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Source must have an HTTP(S) URL")
    # Preserve path, query, scheme and versions; only normalize host and fragment.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def merge_sources(existing, results, round_number):
    registry = copy.deepcopy(existing)
    by_url = {item["canonical_url"]: item for item in registry}
    current = []
    for result in results:
        url = (result.get("url") or "").strip()
        snippet = (result.get("content") or "").strip()
        title = (result.get("title") or "").strip()
        if not url or not snippet or not title:
            continue
        try:
            key = normalize_url(url)
        except ValueError:
            continue
        if key not in by_url:
            item = {"id": f"S{len(registry)+1}", "url": url,
                    "canonical_url": key, "title": title,
                    "first_seen_round": round_number, "observations": []}
            registry.append(item)
            by_url[key] = item
        item = by_url[key]
        observation = {"round": round_number, "title": title, "snippet": snippet}
        if observation not in item["observations"]:
            item["observations"].append(observation)
        current.append(f'[{item["id"]}] {title}\nSearch snippet (not verified full text): {snippet[:4000]}')
    if not current:
        raise ValueError("No usable evidence; refusing to summarize")
    return registry, "\n\n".join(current)


def check_citations(text, registry):
    known = {item["id"] for item in registry}
    cited = set(re.findall(r"\[(S\d+)\]", text))
    unknown = sorted(cited - known)
    urls = re.findall(r"https?://[^\s<>]+", text)
    return {"unknown_ids": unknown, "cited_ids": sorted(cited),
            "uncited_ids": sorted(known - cited), "body_urls": urls,
            "missing_citations": not cited,
            "status": "warning" if unknown or urls or not cited else "passed",
            "scope": "Syntax and membership only; not claim support or citation coverage."}


def render_sources(registry):
    # Escape Markdown labels; URLs originate in retrieved records, never the LLM.
    def label(value):
        return re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", value).replace("\n", " ")
    return "\n".join(f'- [{x["id"]}] {label(x["title"])} — <{x["url"].replace(">", "%3E").replace("<", "%3C")}>' for x in registry)
