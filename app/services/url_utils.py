"""URL parsing helpers used by the documentation and schema layers."""

from urllib.parse import urlsplit


def extract_base_url(url: str) -> str:
    """Return the scheme and netloc portion of a URL."""

    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"Invalid target URL: {url}")
    return f"{parts.scheme}://{parts.netloc}"


def extract_path(url: str) -> str:
    """Return the normalized path from a URL."""

    path = urlsplit(url).path or "/"
    return normalize_path(path)


def normalize_path(path: str) -> str:
    """Normalize paths so route matching is stable."""

    normalized = path.strip() or "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    return normalized


def build_doc_candidates(base_url: str, doc_paths: list[str]) -> list[str]:
    """Build full documentation probe URLs from configured paths."""

    base = base_url.rstrip("/")
    return [f"{base}{normalize_path(path)}" for path in doc_paths]
