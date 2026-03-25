"""
Vector Store Tool — Amazon OpenSearch Serverless
Embeds match notes via Titan Multimodal Embeddings and upserts them into OpenSearch.
"""
import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from config import AWS_REGION, OPENSEARCH_ENDPOINT, OPENSEARCH_INDEX, EMBEDDING_MODEL

# AWS Creds for OpenSearch standard/serverless
credentials = boto3.Session().get_credentials()
if credentials and OPENSEARCH_ENDPOINT:
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, AWS_REGION, 'es', session_token=credentials.token)
    _os_client = OpenSearch(
        hosts=[{'host': OPENSEARCH_ENDPOINT, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
else:
    _os_client = None
    _local_store = []

_bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)


def _embed(text: str) -> list[float]:
    """Generate embeddings using Amazon Titan Multimodal model."""
    body = json.dumps({"inputText": text})
    response = _bedrock_runtime.invoke_model(
        body=body,
        modelId=EMBEDDING_MODEL,
        accept="application/json",
        contentType="application/json"
    )
    response_body = json.loads(response.get('body').read())
    return response_body.get('embedding')


async def upsert_match_notes(doc_id: str, text: str) -> None:
    """Store an embedded chunk of match notes into OpenSearch."""
    if not _os_client:
        _local_store.append({"id": doc_id, "text": text})
        print(f"[LocalStore] Stored '{doc_id}' ({len(text)} chars)")
        return

    vector = _embed(text)
    document = {
        "id": doc_id,
        "text": text,
        "embedding": vector
    }
    _os_client.index(
        index=OPENSEARCH_INDEX,
        body=document,
        id=doc_id
    )


async def retrieve_relevant_context(query: str, top_k: int = 5) -> str:
    """Retrieve top-K semantic matches from OpenSearch using k-NN."""
    if not _os_client:
        # Keyword fallback for local dev
        results = [
            item["text"] for item in _local_store
            if any(word.lower() in item["text"].lower() for word in query.split())
        ]
        return "\n\n---\n\n".join(results[:top_k]) if results else "No relevant match notes found."

    query_vector = _embed(query)
    search_query = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_vector,
                    "k": top_k
                }
            }
        }
    }
    
    try:
        response = _os_client.search(
            body=search_query,
            index=OPENSEARCH_INDEX
        )
        hits = response['hits']['hits']
        return "\n\n---\n\n".join([hit['_source']['text'] for hit in hits])
    except Exception as e:
        print(f"OpenSearch search failed: {e}")
        return "Context retrieval failed."
