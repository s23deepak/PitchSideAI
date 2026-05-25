"""
Multi-Source Retriever — PitchSideAI
Load-balanced soccer data retrieval with round-robin distribution.

Distributes requests across multiple sources to avoid rate limits:
- ESPN (primary, no auth, stable)
- FootballData.org (requires API key, 10 req/min free tier)
- Transfermarkt (scraped, rich player market values/stats)
- OneVersusOne.com (premium stats: 1vs1 Index, progressive carries, pre-assists)
- Firecrawl (fallback with anti-bot handling)

Usage:
    retriever = MultiSourceRetriever()
    stats = await retriever.get_player_stats("Salah", "Liverpool")
    # Automatically rotates: ESPN → FootballData → Transfermarkt → 1v1 → Firecrawl
"""
import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional
from data_sources.cache import DataCache
from data_sources.retrieval_audit import audit_retrieval, monotonic_ms

logger = logging.getLogger(__name__)


class RateLimiter:
    """Track and enforce per-source rate limits."""

    def __init__(self, requests_per_minute: int = 60):
        self._rpm = requests_per_minute
        self._window_start = time.monotonic()
        self._request_count = 0

    async def acquire(self):
        """Wait if necessary to stay within rate limit."""
        now = time.monotonic()
        if now - self._window_start >= 60:
            self._window_start = now
            self._request_count = 0

        if self._request_count >= self._rpm:
            sleep_for = 60 - (now - self._window_start) + 0.5
            if sleep_for > 0:
                logger.debug("Rate limit hit, sleeping %.1fs", sleep_for)
                await asyncio.sleep(sleep_for)
                self._window_start = time.monotonic()
                self._request_count = 0

        self._request_count += 1


class MultiSourceRetriever:
    """
    Load-balanced retriever that distributes requests across multiple data sources.

    Uses round-robin selection with automatic failover on errors.
    Each source has its own rate limiter to prevent throttling.
    """

    def __init__(self, cache: Optional[DataCache] = None, league: str = "ENG-Premier League", season: str = "25-26"):
        self.cache = cache or DataCache(ttl_seconds=1800)
        self._league = league
        self._season = season
        self._round_robin_index = 0

        # Initialize retrievers lazily to avoid import errors
        self._retrievers: List[Any] = []
        self._rate_limiters: Dict[str, RateLimiter] = {}
        self._initialize_retrievers()

    def _initialize_retrievers(self):
        """Initialize available retrievers with their rate limiters."""
        # Load .env file if not already loaded
        from pathlib import Path
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # 1. ESPN - no auth, very stable, high rate limit
        try:
            from data_sources.espn_retriever import ESPNDataRetriever
            self._retrievers.append(("espn", ESPNDataRetriever(cache=self.cache), RateLimiter(120)))
            logger.info("MultiSource: ESPN retriever initialized")
        except Exception as exc:
            logger.warning("MultiSource: Failed to initialize ESPN: %s", exc)

        # 2. FootballData.org - requires API key, 10 req/min free tier
        fd_api_key = os.getenv("FOOTBALL_DATA_API_KEY", "")
        if not fd_api_key:
            logger.warning("MultiSource: FootballData.org skipped (FOOTBALL_DATA_API_KEY not set)")
        else:
            try:
                from data_sources.football_data_retriever import FootballDataRetriever
                fd = FootballDataRetriever(cache=self.cache, api_key=fd_api_key)
                self._retrievers.append(("football_data", fd, RateLimiter(10)))
                logger.info("MultiSource: FootballData.org retriever initialized")
            except Exception as exc:
                logger.warning("MultiSource: Failed to initialize FootballData.org: %s", exc)

        # 3. Transfermarkt - scraped data, moderate rate limit
        try:
            from data_sources.transfermarkt_retriever import TransfermarktRetriever
            tm = TransfermarktRetriever(cache=self.cache)
            if tm.is_available:
                self._retrievers.append(("transfermarkt", tm, RateLimiter(20)))
                logger.info("MultiSource: Transfermarkt retriever initialized")
            else:
                logger.warning("MultiSource: Transfermarkt skipped (not available)")
        except Exception as exc:
            logger.warning("MultiSource: Failed to initialize Transfermarkt: %s", exc)

        # 4. OneVersusOne.com - premium stats, requires login
        # Note: Check credentials directly from environment since .env may not be loaded yet
        ovo_email = os.getenv("1V1_EMAIL", "")
        ovo_password = os.getenv("1V1_PASSWORD", "")
        if not ovo_email or not ovo_password:
            logger.warning("MultiSource: OneVersusOne.com skipped (1V1_EMAIL or 1V1_PASSWORD not set)")
        else:
            try:
                from data_sources.one_versus_one_retriever import OneVersusOneRetriever
                ovo = OneVersusOneRetriever(cache=self.cache, email=ovo_email, password=ovo_password)
                self._retrievers.append(("one_versus_one", ovo, RateLimiter(15)))
                logger.info("MultiSource: OneVersusOne.com retriever initialized")
            except Exception as exc:
                logger.warning("MultiSource: Failed to initialize OneVersusOne.com: %s", exc)

        # 5. Firecrawl - fallback with anti-bot, lower priority
        try:
            from data_sources.firecrawl_retriever import FirecrawlRetriever
            self._retrievers.append(("firecrawl", FirecrawlRetriever(cache=self.cache), RateLimiter(30)))
            logger.info("MultiSource: Firecrawl retriever initialized")
        except Exception as exc:
            logger.warning("MultiSource: Failed to initialize Firecrawl: %s", exc)

        if not self._retrievers:
            logger.error("MultiSource: No retrievers available!")

    @property
    def is_available(self) -> bool:
        return len(self._retrievers) > 0

    @property
    def available_sources(self) -> List[str]:
        """Return list of available source names."""
        return [name for name, _, _ in self._retrievers]

    def _get_next_retriever(self, preferred_index: Optional[int] = None):
        """
        Get next retriever using round-robin with failover.

        Args:
            preferred_index: Start from this index (for retry logic)

        Returns:
            Tuple of (name, retriever, rate_limiter) or (None, None, None) if none available
        """
        if not self._retrievers:
            return None, None, None

        count = len(self._retrievers)
        if preferred_index is not None:
            start = (preferred_index + 1) % count
        else:
            start = self._round_robin_index % count

        for offset in range(count):
            idx = (start + offset) % count
            self._round_robin_index = (idx + 1) % count
            return self._retrievers[idx]

        return None, None, None

    async def _call_with_rate_limit(
        self,
        name: str,
        retriever: Any,
        rate_limiter: RateLimiter,
        method: str,
        *args,
        **kwargs
    ):
        """Call a retriever method while respecting rate limits."""
        await rate_limiter.acquire()
        start_ms = monotonic_ms()
        params = {
            "args": list(args),
            "kwargs": kwargs,
        }
        try:
            result = await getattr(retriever, method)(*args, **kwargs)
            await audit_retrieval(
                provider=name,
                method=method,
                params=params,
                result=result,
                duration_ms=monotonic_ms() - start_ms,
            )
            return result
        except Exception as exc:
            await audit_retrieval(
                provider=name,
                method=method,
                params=params,
                error=exc,
                duration_ms=monotonic_ms() - start_ms,
            )
            logger.warning("%s.%s failed: %s", name, method, exc)
            raise

    async def _race_sources(
        self,
        method: str,
        validator,
        *args,
        max_parallel: int = 2,
        skip_names: Optional[set[str]] = None,
        **kwargs,
    ):
        """Race a small set of sources and return the first useful result."""
        skip_names = skip_names or set()
        candidates = [
            (name, retriever, limiter)
            for name, retriever, limiter in self._retrievers
            if name not in skip_names and hasattr(retriever, method)
        ][:max_parallel]
        if not candidates:
            return None, None, []

        async def _call_source(name: str, retriever: Any, limiter: RateLimiter):
            try:
                result = await self._call_with_rate_limit(name, retriever, limiter, method, *args, **kwargs)
                return name, result, None
            except Exception as exc:
                return name, None, exc

        tasks = [asyncio.create_task(_call_source(name, retriever, limiter)) for name, retriever, limiter in candidates]
        errors = []
        try:
            for completed in asyncio.as_completed(tasks):
                name, result, error = await completed
                if error:
                    errors.append(f"{name}: {error}")
                    continue
                if validator(result):
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    return name, result, errors
            return None, None, errors
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def get_player_stats(
        self,
        player_name: str,
        team_name: str,
        sport: str = "soccer"
    ) -> Dict[str, Any]:
        """
        Fetch player stats with automatic source rotation.

        Returns first non-empty result, trying up to 3 sources.
        """
        cache_key = f"{player_name}|{team_name}|{sport}"
        cached = self.cache.get("multi_player", cache_key)
        if cached:
            return cached

        name, result, errors = await self._race_sources(
            "get_player_stats",
            lambda r: bool(r and (not isinstance(r, dict) or r.get("error") is None)),
            player_name,
            team_name,
            sport,
            max_parallel=2,
        )
        if result:
            merged = {**result, "data_source": name}
            self.cache.set("multi_player", cache_key, merged)
            return merged

        logger.warning("All sources failed for player %s/%s: %s", player_name, team_name, errors)
        return {"name": player_name, "team": team_name, "stats": {}, "error": "All sources failed"}

    async def get_team_squad(self, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """Fetch team squad with player list."""
        cache_key = f"{team_name}|{sport}"
        cached = self.cache.get("multi_squad", cache_key)
        if cached:
            return cached

        # CRITICAL: Always try ESPN first for squad data (most reliable, no race condition)
        # Don't use round-robin for squad data - it causes race conditions in parallel fetches
        for name, retriever, limiter in self._retrievers:
            if name != "espn":
                continue

            try:
                result = await self._call_with_rate_limit(
                    name, retriever, limiter, "get_team_squad", team_name, sport
                )
                if result and result.get("players"):
                    self.cache.set("multi_squad", cache_key, {**result, "data_source": name})
                    return result
            except Exception as exc:
                logger.warning("ESPN squad fetch failed: %s", exc)
                break

        # ESPN failed - fall back to round-robin for other sources
        for attempt in range(min(3, len(self._retrievers))):
            name, retriever, limiter = self._get_next_retriever()
            if not retriever or name == "espn":  # Skip ESPN (already tried)
                continue

            try:
                result = await self._call_with_rate_limit(
                    name, retriever, limiter, "get_team_squad", team_name, sport
                )
                if result and result.get("players"):
                    self.cache.set("multi_squad", cache_key, {**result, "data_source": name})
                    return result
            except Exception as exc:
                logger.warning("%s squad fetch failed: %s", name, exc)
                continue

        return {"team": team_name, "players": [], "error": "All sources failed"}

    async def get_recent_form(self, team_name: str, sport: str = "soccer", num_games: int = 5) -> Dict[str, Any]:
        """Fetch team's recent form (last N results)."""
        cache_key = f"{team_name}|{sport}|{num_games}"
        cached = self.cache.get("multi_form", cache_key)
        if cached:
            return cached

        name, result, _errors = await self._race_sources(
            "get_recent_form",
            lambda r: bool(r and r.get("form_string") != "UNKNOWN"),
            team_name,
            sport,
            num_games,
            max_parallel=2,
        )
        if result:
            merged = {**result, "data_source": name}
            self.cache.set("multi_form", cache_key, merged)
            return merged

        return {"team": team_name, "form_string": "UNKNOWN", "error": "All sources failed"}

    async def get_head_to_head(self, team1: str, team2: str, sport: str = "soccer") -> Dict[str, Any]:
        """Fetch head-to-head record between two teams."""
        cache_key = f"{team1}|{team2}|{sport}"
        cached = self.cache.get("multi_h2h", cache_key)
        if cached:
            return cached

        for attempt in range(min(3, len(self._retrievers))):
            name, retriever, limiter = self._get_next_retriever()
            if not retriever:
                break

            try:
                result = await self._call_with_rate_limit(
                    name, retriever, limiter, "get_head_to_head", team1, team2, sport
                )
                if result and result.get("total_matches", 0) > 0:
                    merged = {**result, "data_source": name}
                    self.cache.set("multi_h2h", cache_key, merged)
                    return merged
            except Exception as exc:
                continue

        return {"team1": team1, "team2": team2, "total_matches": 0, "recent_results": []}

    async def get_team_news(self, team_name: str, sport: str = "soccer") -> List[Dict[str, Any]]:
        """Fetch recent news for a team."""
        cache_key = f"{team_name}|{sport}"
        cached = self.cache.get("multi_news", cache_key)
        # Only return cached result if it has actual content (not empty list)
        if cached and isinstance(cached, list) and len(cached) > 0:
            return cached

        name, result, _errors = await self._race_sources(
            "get_team_news",
            lambda r: bool(r and len(r) > 0),
            team_name,
            sport,
            max_parallel=2,
        )
        if result:
            self.cache.set("multi_news", cache_key, result)
            logger.info(f"Found {len(result)} news items from {name}")
            return result

        # Don't cache empty results - try fresh next time
        return []

    async def get_injuries(self, team_name: str, sport: str = "soccer") -> List[Dict[str, Any]]:
        """Fetch injured players for a team."""
        cache_key = f"{team_name}|{sport}"
        cached = self.cache.get("multi_injuries", cache_key)
        if cached:
            return cached

        _name, result, _errors = await self._race_sources(
            "get_injuries",
            lambda r: bool(r),
            team_name,
            sport,
            max_parallel=2,
        )
        if result:
            self.cache.set("multi_injuries", cache_key, result)
            return result

        return []

    async def get_match_context(self, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """Fetch upcoming match datetime and venue."""
        cache_key = f"{team_name}|{sport}"
        cached = self.cache.get("multi_match", cache_key)
        if cached:
            return cached

        for attempt in range(min(2, len(self._retrievers))):
            name, retriever, limiter = self._get_next_retriever()
            if not retriever:
                break

            try:
                result = await self._call_with_rate_limit(
                    name, retriever, limiter, "get_match_context", team_name, sport
                )
                if result:
                    self.cache.set("multi_match", cache_key, result)
                    return result
            except Exception as exc:
                continue

        from datetime import datetime, timezone
        return {"date": datetime.now(timezone.utc).isoformat(), "venue": "Unknown"}

    async def close(self) -> None:
        """Cleanup any open connections."""
        for name, retriever, _ in self._retrievers:
            try:
                if hasattr(retriever, "close"):
                    await retriever.close()
            except Exception as exc:
                logger.warning("Error closing %s: %s", name, exc)
