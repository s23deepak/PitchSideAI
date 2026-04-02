"""
Research Agent — Amazon Nova Pro + Advanced RAG
Builds pre-match briefs and answers live research queries.
"""
import asyncio
from typing import Dict, List, Optional

from agents.base import ResearchAgent as BaseResearchAgent
from config.prompts import get_research_prompt, get_query_prompt
from rag import get_rag_retriever


class ResearchAgent(BaseResearchAgent):
    """
    Researches match-specific information using Nova Pro and stores in RAG.
    Dynamically adapts to any sport type.
    """

    def __init__(self, model_id: str = None, sport: str = "soccer"):
        from config import RESEARCH_MODEL
        super().__init__(model_id or RESEARCH_MODEL, sport)
        self.retriever = get_rag_retriever()

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
        away_team: Optional[str] = None
    ) -> str:
        """
        Answer live fan questions using RAG context and Nova Pro.

        Args:
            query: Fan question
            home_team: Optional - home team for context
            away_team: Optional - away team for context

        Returns:
            Answer text
        """
        self.log_event("query_received", {
            "query": query[:100],  # Log first 100 chars
            "has_team_context": home_team is not None
        })

        # Retrieve relevant context using RAG
        retrieved_docs = await self.retriever.retrieve(
            query,
            top_k=5
        )

        context = "\n\n---\n\n".join([
            f"[{doc.strategy_used}] {doc.text[:500]}"
            for doc in retrieved_docs
        ])

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

