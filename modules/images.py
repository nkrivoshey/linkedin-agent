# modules/images.py — полная замена файла
import logging
import random
import urllib.parse

import requests

logger = logging.getLogger(__name__)

FALLBACK_QUERIES = [
    "data analytics dashboard",
    "business intelligence visualization",
    "machine learning abstract",
    "data science code",
    "technology innovation",
    "professional office data",
]

_IMAGE_STYLE = (
    "clean data visualization aesthetic, minimalist infographic, "
    "professional, dark background, subtle blue accent lines, no text overlays"
)

_CANDIDATES_PER_QUERY = 6
_MAX_CANDIDATES = 15


class ImageFetcher:
    def __init__(
        self,
        unsplash_key: str,
        use_dalle: bool = False,
        openai_key: str = "",
        huggingface_key: str = "",
    ):
        self.unsplash_key = unsplash_key
        self.use_dalle = use_dalle
        self.openai_key = openai_key
        self.huggingface_key = huggingface_key
        self._used_ids: set[str] = set()

    def get_image(self, image_prompt: str, fallback_query: str) -> str:
        """Main entry point. Tier 1: DALL-E 3 (if enabled) or Pollinations.ai. Tier 2: Unsplash."""
        if image_prompt and self.use_dalle and self.openai_key:
            url = self._fetch_dalle_prompt(image_prompt)
            if url:
                logger.info("Image: generated via DALL-E 3")
                return url
        if image_prompt:
            url = self.generate_image(image_prompt)
            if url:
                logger.info("Image: generated via Pollinations.ai")
                return url
        url = self.fetch_image(fallback_query or random.choice(FALLBACK_QUERIES))
        if url:
            logger.info("Image: fetched from Unsplash (fallback)")
        else:
            logger.warning("Image: all sources failed — publishing without image")
        return url

    def generate_image(self, prompt: str) -> str:
        """Tier 1: free generation via Pollinations.ai. Returns URL or empty string."""
        full_prompt = f"{prompt}, {_IMAGE_STYLE}"
        encoded = urllib.parse.quote(full_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}"
        try:
            resp = requests.get(url, timeout=45, stream=True)
            try:
                content_type = resp.headers.get("content-type", "")
                if resp.status_code == 200 and "image" in content_type:
                    return url
                logger.warning("Pollinations: status=%d content-type=%s", resp.status_code, content_type)
            finally:
                resp.close()
        except Exception as e:
            logger.warning("Pollinations did not respond: %s", e)
        return ""

    def fetch_image(self, query: str) -> str:
        """Tier 2: keyword search via Unsplash. Returns URL or empty string."""
        candidates = self.fetch_candidates([query])
        if not candidates:
            return ""
        fresh = [c for c in candidates if c["id"] not in self._used_ids]
        pick = random.choice(fresh) if fresh else random.choice(candidates)
        self._used_ids.add(pick["id"])
        if len(self._used_ids) > 100:
            self._used_ids.clear()
        return pick["url"]

    def fetch(self, keywords: list[str]) -> str:
        """Deprecated — kept for backward compatibility."""
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
                params={"query": query, "per_page": per_page, "page": page, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {self.unsplash_key}"},
                timeout=10,
            )
        except Exception:
            return []
        if resp.status_code != 200:
            return []
        return resp.json().get("results", [])

    def _fetch_dalle_prompt(self, prompt: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            full_prompt = f"{prompt}. Professional, clean, suitable for LinkedIn post."
            response = client.images.generate(model="dall-e-3", prompt=full_prompt[:4000], size="1024x1024", n=1)
            return response.data[0].url
        except Exception as e:
            logger.warning("DALL-E 3 failed: %s", e)
            return ""

    def _fetch_dalle(self, keywords: list[str]) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            prompt = f"Professional photo: {', '.join(keywords[:3])}. Clean, modern, suitable for LinkedIn."
            response = client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", n=1)
            return response.data[0].url
        except Exception:
            return self.fetch(keywords)
