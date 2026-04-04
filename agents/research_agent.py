"""
Research Agent — Amazon Nova Pro + Advanced RAG
Builds pre-match briefs and answers live research queries.
"""
import asyncio
import re
from typing import Dict, List, Optional

import httpx

from agents.base import ResearchAgent as BaseResearchAgent
from config.prompts import get_research_prompt, get_query_prompt
from data_sources.factory import get_retriever, get_search_service
from data_sources.football_data_retriever import TEAM_IDS
from rag import RetrievedDocument, get_rag_retriever


class ResearchAgent(BaseResearchAgent):
    """
    Researches match-specific information using Nova Pro and stores in RAG.
    Dynamically adapts to any sport type.
    """

    def __init__(self, model_id: str = None, sport: str = "soccer"):
        from config import RESEARCH_MODEL
        super().__init__(model_id or RESEARCH_MODEL, sport)
        self.retriever = get_rag_retriever()
        self.team_retriever = get_retriever(sport)
        self.search_service = get_search_service()

    async def execute(self, home_team: str, away_team: str) -> str:
        """Alias for build_match_brief for orchestration compatibility."""
        return await self.build_match_brief(home_team, away_team)

    async def build_match_brief(self, home_team: str, away_team: str) -> str:
        """
        Build comprehensive pre-match brief with dynamic sport-specific content.

        Args:
            home_team: Home team name
            away_team: Away team name

        Returns:
            Brief text and indexed in RAG
        """
        self.log_event("brief_generation_started", {
            "home_team": home_team,
            "away_team": away_team
        })

        # Get dynamic prompt based on sport
        prompt = get_research_prompt(home_team, away_team, self.sport)

        # Call model
        brief_text = await self.call_bedrock(
            prompt,
            temperature=0.5,
            max_tokens=2000
        )

        # Chunk and index for RAG
        await self._index_brief(home_team, away_team, brief_text)

        self.log_event("brief_generation_completed", {
            "home_team": home_team,
            "away_team": away_team,
            "brief_length": len(brief_text)
        })

        return brief_text

    async def answer_live_query(
        self,
        query: str,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
        retrieved_docs: Optional[List[RetrievedDocument]] = None,
        supplemental_context: Optional[str] = None
    ) -> str:
        """
        Answer live fan questions using RAG context and Nova Pro.

        Args:
            query: Fan question
            home_team: Optional - home team for context
            away_team: Optional - away team for context
            retrieved_docs: Optional pre-fetched RAG documents
            supplemental_context: Optional live/session context to append

        Returns:
            Answer text
        """
        self.log_event("query_received", {
            "query": query[:100],  # Log first 100 chars
            "has_team_context": home_team is not None,
            "has_prefetched_context": retrieved_docs is not None
        })

        grounded_team_fact_answer = await self._answer_grounded_team_fact_query(
            query,
            home_team,
            away_team,
        )
        if grounded_team_fact_answer:
            self.log_event("query_answered_from_grounded_team_fact", {
                "query": query[:100],
                "answer_length": len(grounded_team_fact_answer)
            })
            return grounded_team_fact_answer

        # Retrieve relevant context using RAG unless the caller already provided it.
        if retrieved_docs is None:
            retrieved_docs = await self.retriever.retrieve(
                query,
                top_k=5
            )

        retrieved_context = "\n\n---\n\n".join([
            f"[{doc.strategy_used}] {doc.text[:500]}"
            for doc in retrieved_docs
        ])

        context_parts = []
        if supplemental_context:
            context_parts.append(supplemental_context)
        if retrieved_context:
            context_parts.append(retrieved_context)

        context = "\n\n---\n\n".join(context_parts) if context_parts else "No match-specific context available."

        # Get dynamic prompt based on sport
        prompt = get_query_prompt(context, query, self.sport)

        # Answer
        answer = await self.call_bedrock(
            prompt,
            temperature=0.3,
            max_tokens=300
        )

        self.log_event("query_answered", {
            "query": query[:100],
            "context_documents": len(retrieved_docs),
            "answer_length": len(answer)
        })

        return answer

    async def _answer_grounded_team_fact_query(
        self,
        query: str,
        home_team: Optional[str],
        away_team: Optional[str],
    ) -> Optional[str]:
        """Handle current team fact questions with grounded sources only."""
        intent = self._detect_team_fact_intent(query)
        if not intent:
            return None

        team_name = self._extract_team_name(query, home_team, away_team)
        if not team_name:
            return "I couldn't determine which team you're asking about."

        if intent == "manager":
            return await self._answer_manager_query(query, team_name)
        if intent == "captain":
            return await self._answer_captain_query(team_name)
        if intent == "injuries":
            return await self._answer_injury_query(team_name)
        if intent == "signings":
            return await self._answer_signings_query(query, team_name)

        return None

    async def _answer_manager_query(self, query: str, team_name: str) -> str:
        """Answer current manager/head coach questions from grounded sources."""
        wikipedia_manager = await self._lookup_team_wikipedia_field(
            team_name,
            ("manager", "head coach", "coach"),
        )
        if wikipedia_manager:
            return f"{self._display_team_name(team_name)}'s manager is {wikipedia_manager}."

        if not self.search_service or not self.search_service.is_available:
            return (
                f"I couldn't verify the current manager for {self._display_team_name(team_name)} "
                "from the live sources I have available."
            )

        search_result = await self.search_service.search_team_manager(team_name, self.sport)
        answer = await self._answer_from_search_evidence(
            query,
            team_name,
            search_result,
            failure_message=(
                f"I couldn't verify the current manager for {self._display_team_name(team_name)} "
                "from the live search results I checked."
            ),
            answer_instructions=(
                "Identify the current manager or head coach only if the evidence clearly supports it."
            ),
        )
        return answer

    async def _answer_captain_query(self, team_name: str) -> str:
        """Answer current captain questions from the team's Wikipedia page."""
        wikipedia_captain = await self._lookup_team_wikipedia_field(
            team_name,
            ("captain", "club captain"),
        )
        if not wikipedia_captain:
            wikipedia_captain = await self._lookup_team_wikipedia_captain(team_name)

        if wikipedia_captain:
            return f"{self._display_team_name(team_name)}'s captain is {wikipedia_captain}."

        return (
            f"I couldn't verify the current captain for {self._display_team_name(team_name)} "
            "from the grounded sources I checked."
        )

    async def _answer_injury_query(self, team_name: str) -> str:
        """Answer current injury questions from live roster data."""
        try:
            squad = await self.team_retriever.get_team_squad(team_name, self.sport)
        except Exception as exc:
            self.logger.warning("team_squad_lookup_failed", team_name=team_name, error=str(exc))
            squad = {}

        players = squad.get("players", [])
        has_live_roster = bool(players) and bool(squad.get("team_id") or squad.get("player_count"))

        if has_live_roster:
            injuries = [
                {
                    "player": player.get("name", "Unknown"),
                    "status": player.get("injury_status", "Unavailable"),
                }
                for player in players
                if player.get("injury_status") not in ("Healthy", "", None)
            ]
            if injuries:
                summary = ", ".join(
                    f"{item['player']} ({item['status']})"
                    for item in injuries[:5]
                )
                if len(injuries) > 5:
                    summary += ", plus additional listed absences"
                return (
                    f"The latest ESPN squad data lists these current {self._display_team_name(team_name)} injuries or absences: "
                    f"{summary}."
                )

            return (
                f"I found no current injuries listed in the latest ESPN squad data for {self._display_team_name(team_name)}."
            )

        return (
            f"I couldn't verify the current injury list for {self._display_team_name(team_name)} "
            "from the live roster data I have access to."
        )

    async def _answer_signings_query(self, query: str, team_name: str) -> str:
        """Answer recent signings questions from current news evidence only."""
        espn_news = []
        tavily_result = {"answer": "", "results": []}

        try:
            espn_news = await self.team_retriever.get_team_news(team_name, self.sport)
        except Exception as exc:
            self.logger.warning("team_news_lookup_failed", team_name=team_name, error=str(exc))

        if self.search_service and self.search_service.is_available:
            try:
                tavily_result = await self.search_service.search_team_signings(team_name, self.sport)
            except Exception as exc:
                self.logger.warning("team_signings_search_failed", team_name=team_name, error=str(exc))

        evidence_parts = []
        relevant_espn_news = self._filter_signing_news(espn_news)
        if relevant_espn_news:
            evidence_parts.append(
                "ESPN NEWS:\n" + "\n\n".join(
                    f"TITLE: {item.get('headline', '')}\nDETAIL: {item.get('description', '')[:280]}\nURL: {item.get('url', '')}"
                    for item in relevant_espn_news[:5]
                )
            )

        tavily_answer = (tavily_result.get("answer") or "").strip()
        tavily_results = tavily_result.get("results", [])[:5]
        if tavily_answer:
            evidence_parts.append(f"TAVILY SUMMARY:\n{tavily_answer}")
        if tavily_results:
            evidence_parts.append(
                "TAVILY RESULTS:\n" + "\n\n".join(
                    f"TITLE: {item.get('title', '')}\nSNIPPET: {item.get('content', '')[:280]}\nURL: {item.get('url', '')}"
                    for item in tavily_results
                )
            )

        if not evidence_parts:
            return (
                f"I couldn't verify recent signings for {self._display_team_name(team_name)} "
                "from the current news sources I checked."
            )

        prompt = f"""
You are answering a sports transfer question using ONLY the evidence below.

QUESTION: {query}
TEAM: {self._display_team_name(team_name)}

EVIDENCE:
{"\n\n".join(evidence_parts)}

Rules:
- Use only the evidence above.
- Mention only signings or transfer arrivals that are clearly supported by the evidence.
- If the evidence is ambiguous or does not confirm any recent signings, say that recent signings could not be verified from the available sources.
- Keep the answer to 1-2 sentences.

Answer:
"""

        return await self.call_bedrock(
            prompt,
            temperature=0.1,
            max_tokens=140,
        )

    async def _lookup_team_wikipedia_field(
        self,
        team_name: str,
        field_names: tuple[str, ...],
    ) -> Optional[str]:
        """Extract a field from a team's Wikipedia page wikitext."""
        wikitext = await self._get_team_wikipedia_wikitext(team_name)
        if not wikitext:
            return None

        for field_name in field_names:
            pattern = rf"\|\s*{re.escape(field_name)}\s*=\s*(.+)"
            match = re.search(pattern, wikitext, flags=re.IGNORECASE)
            if not match:
                continue
            cleaned = self._clean_wiki_value(match.group(1))
            if cleaned:
                return cleaned

        return None

    async def _lookup_team_wikipedia_captain(self, team_name: str) -> Optional[str]:
        """Extract the current captain from a team's Wikipedia squad table."""
        wikitext = await self._get_team_wikipedia_wikitext(team_name)
        if not wikitext:
            return None

        captain_patterns = (
            r"\{\{Fs player\|[^\n}]*\|name=\[\[(?:[^\]|]+\|)?([^\]]+)\]\][^\n}]*\|other=\[\[Captain",
            r"\{\{Fs player\|[^\n}]*\|other=\[\[Captain[^\n}]*\|name=\[\[(?:[^\]|]+\|)?([^\]]+)\]\]",
        )
        for pattern in captain_patterns:
            match = re.search(pattern, wikitext, flags=re.IGNORECASE)
            if match:
                cleaned = self._clean_wiki_value(match.group(1))
                if cleaned:
                    return cleaned

        return None

    async def _get_team_wikipedia_wikitext(self, team_name: str) -> Optional[str]:
        """Fetch a team's Wikipedia page source as wikitext."""
        headers = {"User-Agent": "PitchAI/1.0 (local-dev)"}
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": f"{team_name} football club",
            "format": "json",
            "srlimit": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                search_response = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params=search_params,
                )
                search_response.raise_for_status()
                search_results = search_response.json().get("query", {}).get("search", [])
                if not search_results:
                    return None

                page_title = search_results[0].get("title")
                if not page_title:
                    return None

                parse_response = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "parse",
                        "page": page_title,
                        "prop": "wikitext",
                        "format": "json",
                    },
                )
                parse_response.raise_for_status()
                wikitext = (
                    parse_response.json()
                    .get("parse", {})
                    .get("wikitext", {})
                    .get("*", "")
                )
        except Exception as exc:
            self.logger.warning("wikipedia_team_lookup_failed", team_name=team_name, error=str(exc))
            return None
        return wikitext

    async def _answer_from_search_evidence(
        self,
        query: str,
        team_name: str,
        search_result: Dict[str, object],
        failure_message: str,
        answer_instructions: str,
    ) -> str:
        """Generate an answer from web-search evidence only."""
        answer = str(search_result.get("answer") or "").strip()
        results = list(search_result.get("results") or [])[:3]

        evidence_parts = []
        if answer:
            evidence_parts.append(f"SEARCH SUMMARY:\n{answer}")
        if results:
            snippets = "\n\n".join(
                f"TITLE: {result.get('title', '')}\nURL: {result.get('url', '')}\nSNIPPET: {result.get('content', '')[:300]}"
                for result in results
            )
            evidence_parts.append(f"TOP RESULTS:\n{snippets}")

        if not evidence_parts:
            return failure_message

        prompt = f"""
You are answering a sports fact question using ONLY the web-search evidence below.

QUESTION: {query}
TEAM: {self._display_team_name(team_name)}

WEB EVIDENCE:
{"\n\n".join(evidence_parts)}

Rules:
- Use only the evidence above.
- {answer_instructions}
- If the evidence is not clear enough, respond with this exact sentence: {failure_message}
- Do not use prior knowledge.
- Keep the answer to 1-2 sentences.

Answer:
"""

        return await self.call_bedrock(
            prompt,
            temperature=0.1,
            max_tokens=120,
        )

    def _clean_wiki_value(self, value: str) -> str:
        """Normalize a raw Wikipedia infobox field into plain text."""
        cleaned = value.split("\n", 1)[0].strip()
        cleaned = re.sub(r"\{\{.*?\}\}", "", cleaned)
        cleaned = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", cleaned)
        cleaned = re.sub(r"<.*?>", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip(" ,")

    def _detect_team_fact_intent(self, query: str) -> Optional[str]:
        """Identify grounded team fact queries that should bypass free-form answering."""
        lowered = query.lower()
        if any(term in lowered for term in ("injuries", "injured", "injury list", "absentees", "availability")):
            return "injuries"
        if any(term in lowered for term in ("recent signings", "new signings", "signings", "transfer arrivals", "transfers in")):
            return "signings"
        if "captain" in lowered or "vice-captain" in lowered:
            return "captain"
        if any(term in lowered for term in ("manager", "head coach", "coach", "boss")):
            return "manager"
        return None

    def _filter_signing_news(self, news_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Keep only news items likely to describe transfer arrivals or signings."""
        keywords = (
            "sign",
            "signed",
            "signing",
            "transfer",
            "joins",
            "joined",
            "arrival",
            "deal",
            "loan",
            "recruit",
        )
        filtered = []
        for item in news_items:
            haystack = " ".join(
                [
                    item.get("headline", ""),
                    item.get("description", ""),
                ]
            ).lower()
            if any(keyword in haystack for keyword in keywords):
                filtered.append(item)
        return filtered

    def _display_team_name(self, team_name: str) -> str:
        """Format a team name for user-facing answers."""
        return team_name.title()

    def _extract_team_name(
        self,
        query: str,
        home_team: Optional[str],
        away_team: Optional[str],
    ) -> Optional[str]:
        lowered = query.lower()

        candidates = []
        for team_name in (home_team, away_team):
            if team_name:
                candidates.append(team_name)
        candidates.extend(sorted(TEAM_IDS.keys(), key=len, reverse=True))

        for candidate in candidates:
            if candidate and candidate.lower() in lowered:
                return candidate

        patterns = (
            r"(?:manager|coach|captain) of ([a-z][a-z .&-]+)",
            r"(?:injuries|injury list|injured players) (?:for|at) ([a-z][a-z .&-]+)",
            r"(?:recent signings|new signings|signings|transfer arrivals|transfers) (?:for|by|of) ([a-z][a-z .&-]+)",
            r"([a-z][a-z .&-]+)'s (?:manager|coach|captain|injuries|injury list|recent signings|signings|transfers)",
        )
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                extracted = match.group(1).strip(" ?!.,")
                if extracted:
                    return extracted

        return None

    async def _index_brief(self, home_team: str, away_team: str, brief_text: str) -> None:
        """
        Index brief chunks in RAG for later retrieval.

        Args:
            home_team: Home team name
            away_team: Away team name
            brief_text: Brief text to index
        """
        chunks = self._chunk_text(brief_text, chunk_size=500)
        match_id = f"{home_team.lower().replace(' ', '_')}_{away_team.lower().replace(' ', '_')}"

        # Index chunks concurrently
        tasks = []
        for i, chunk in enumerate(chunks):
            doc_id = f"{match_id}_chunk_{i}"
            metadata = {
                "match_id": match_id,
                "home_team": home_team,
                "away_team": away_team,
                "sport": self.sport,
                "chunk_index": i,
                "chunk_count": len(chunks)
            }

            task = self.retriever.index_document(doc_id, chunk, metadata)
            tasks.append(task)

        # Wait for all indexing to complete
        await asyncio.gather(*tasks)

        self.logger.info(
            "brief_indexed",
            match_id=match_id,
            chunks_indexed=len(chunks)
        )

    async def research_multiple_topics(
        self,
        home_team: str,
        away_team: str,
        topics: List[str]
    ) -> Dict[str, str]:
        """
        Research specific topics for more focused briefs.

        Args:
            home_team: Home team
            away_team: Away team
            topics: List of specific topics to research

        Returns:
            Dict mapping topic -> research results
        """
        topics_str = "\n".join([f"- {t}" for t in topics])

        prompt = f"""
You are a professional {self.sport} analyst.

Research the following for {home_team} vs {away_team}:

{topics_str}

Provide specific, data-driven insights for each topic.
"""

        response = await self.call_bedrock(prompt, temperature=0.5, max_tokens=1500)

        results = {}
        current_topic = None
        current_text = []

        for line in response.split('\n'):
            for topic in topics:
                if topic.lower() in line.lower():
                    if current_topic:
                        results[current_topic] = '\n'.join(current_text).strip()
                    current_topic = topic
                    current_text = [line]
                    break
            else:
                if current_topic:
                    current_text.append(line)

        if current_topic:
            results[current_topic] = '\n'.join(current_text).strip()

        return results

