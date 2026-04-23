import random
import requests

FALLBACK_QUERIES = [
    "data analytics dashboard",
    "artificial intelligence technology",
    "business intelligence",
    "machine learning abstract",
    "data science visualization",
    "technology innovation",
]

_CANDIDATES_PER_QUERY = 6
_MAX_CANDIDATES = 15


class ImageFetcher:
    def __init__(self, unsplash_key: str, use_dalle: bool = False, openai_key: str = ""):
        self.unsplash_key = unsplash_key
        self.use_dalle = use_dalle
        self.openai_key = openai_key
        self._used_ids: set[str] = set()

    def fetch(self, keywords: list[str]) -> str:
        """Simple fetch — returns first good result. Used as fallback."""
        if self.use_dalle and self.openai_key:
            return self._fetch_dalle(keywords)
        candidates = self.fetch_candidates(keywords)
        if not candidates:
            return ""
        fresh = [c for c in candidates if c["id"] not in self._used_ids]
        pick = random.choice(fresh) if fresh else random.choice(candidates)
        self._used_ids.add(pick["id"])
        if len(self._used_ids) > 100:
            self._used_ids.clear()
        return pick["url"]

    def fetch_candidates(self, keywords: list[str]) -> list[dict]:
        """
        Fetch up to _MAX_CANDIDATES photos with metadata across all keywords.
        Returns list of {id, url, description, alt_description, tags}.
        """
        queries = keywords[:3] if keywords else [random.choice(FALLBACK_QUERIES)]
        seen_ids: set[str] = set()
        candidates: list[dict] = []

        for query in queries:
            if len(candidates) >= _MAX_CANDIDATES:
                break
            page = random.randint(1, 4)
            results = self._search_raw(query, page=page, per_page=_CANDIDATES_PER_QUERY)
            if not results and page > 1:
                results = self._search_raw(query, page=1, per_page=_CANDIDATES_PER_QUERY)
            for r in results:
                if r["id"] in seen_ids or r["id"] in self._used_ids:
                    continue
                seen_ids.add(r["id"])
                tags = [t["title"] for t in r.get("tags", []) if isinstance(t, dict)]
                candidates.append({
                    "id": r["id"],
                    "url": r["urls"]["regular"],
                    "description": r.get("description") or "",
                    "alt_description": r.get("alt_description") or "",
                    "tags": tags,
                })
            if len(candidates) < _CANDIDATES_PER_QUERY:
                # current query gave few results — also try fallback query
                fb = random.choice(FALLBACK_QUERIES)
                for r in self._search_raw(fb, page=1, per_page=_CANDIDATES_PER_QUERY):
                    if r["id"] in seen_ids or r["id"] in self._used_ids:
                        continue
                    seen_ids.add(r["id"])
                    tags = [t["title"] for t in r.get("tags", []) if isinstance(t, dict)]
                    candidates.append({
                        "id": r["id"],
                        "url": r["urls"]["regular"],
                        "description": r.get("description") or "",
                        "alt_description": r.get("alt_description") or "",
                        "tags": tags,
                    })

        return candidates[:_MAX_CANDIDATES]

    def mark_used(self, image_url: str, candidates: list[dict]) -> None:
        for c in candidates:
            if c["url"] == image_url:
                self._used_ids.add(c["id"])
                if len(self._used_ids) > 100:
                    self._used_ids.clear()
                return

    def _search_raw(self, query: str, page: int = 1, per_page: int = 10) -> list[dict]:
        try:
            resp = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": per_page, "page": page,
                        "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {self.unsplash_key}"},
                timeout=10,
            )
        except Exception:
            return []
        if resp.status_code != 200:
            return []
        return resp.json().get("results", [])

    def _fetch_dalle(self, keywords: list[str]) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            prompt = f"Professional photo: {', '.join(keywords[:3])}. Clean, modern, suitable for LinkedIn."
            response = client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", n=1)
            return response.data[0].url
        except Exception:
            return self.fetch(keywords)
