"""
Research Agent — Amazon Nova 2 Pro + Bedrock AgentCore + OpenSearch RAG
Builds the pre-match "Commentator's Brief" and answers live research queries.
"""
import json
import boto3

from config import AWS_REGION, RESEARCH_MODEL
from tools.vector_store import upsert_match_notes, retrieve_relevant_context

# Initialize Bedrock client
_bedrock = boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)


class ResearchAgent:
    """
    Uses Amazon Nova 2 Pro to autonomously research match-specific information 
    and store it in Amazon OpenSearch Serverless for RAG.
    """

    def __init__(self):
        self.model_id = RESEARCH_MODEL

    async def build_match_brief(self, home_team: str, away_team: str, sport: str = "soccer") -> str:
        """
        Builds the Commentator's Brief and stores chunks in OpenSearch.
        Returns: Summary of the brief as a string.
        """
        prompt = f"""
        You are a professional sports analyst preparing for a live {sport} match.
        Research the following match and produce a structured Commentator's Brief:

        Match: {home_team} vs {away_team}

        Include:
        1. Each team's current form (last 5 matches).
        2. Key player stats (goals, assists, injury updates).
        3. Historical head-to-head record.
        4. Tactical tendencies: pressing style, formation, set-piece patterns.
        """

        messages = [{"role": "user", "content": [{"text": prompt}]}]
        
        # Call Nova 2 Pro via Converse API
        response = _bedrock.converse(
            modelId=self.model_id,
            messages=messages,
            inferenceConfig={"temperature": 0.5}
        )
        brief_text = response['output']['message']['content'][0]['text']

        # Chunk and store in Amazon OpenSearch for live RAG
        chunks = self._chunk_text(brief_text, chunk_size=500)
        for i, chunk in enumerate(chunks):
            doc_id = f"{home_team.lower().replace(' ', '_')}_vs_{away_team.lower().replace(' ', '_')}_chunk_{i}"
            await upsert_match_notes(doc_id, chunk)

        return brief_text

    async def answer_live_query(self, query: str) -> str:
        """
        Retrieves relevant match notes from OpenSearch (RAG) and uses Nova 2 Pro 
        to answer a live tactical or statistical question.
        """
        context = await retrieve_relevant_context(query, top_k=3)

        prompt = f"""
        You are a real-time sports analyst assistant.

        MATCH CONTEXT (pre-researched notes from Amazon OpenSearch):
        {context}

        QUESTION: {query}

        Answer concisely in 2-3 sentences, citing specific stats where possible from the context.
        """
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        response = _bedrock.converse(
            modelId=self.model_id,
            messages=messages,
            inferenceConfig={"temperature": 0.3}
        )
        return response['output']['message']['content'][0]['text']

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 500) -> list[str]:
        words = text.split()
        return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
