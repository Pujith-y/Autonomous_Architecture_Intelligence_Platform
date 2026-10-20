
from qdrant_client import QdrantClient

from app.knowledge_graph.semantic.document_builder import SemanticDocument
from app.knowledge_graph.semantic.embedding_provider import EmbeddingProvider
from app.knowledge_graph.semantic.vector_store import QdrantVectorStore


COLLECTION = "aaip_semantic_smoke_test"

client = QdrantClient(url="http://aaip-qdrant:6333")
store = QdrantVectorStore(client, collection_name=COLLECTION)
provider = EmbeddingProvider()

documents = [
    SemanticDocument(
        entity_id="python.auth.login",
        text=(
            "Entity kind: function\n"
            "Name: login\n"
            "Source code:\n"
            "def login(username, password):\n"
            "    return authenticate(username, password)"
        ),
        metadata={
            "kind": "function",
            "name": "login",
            "file": "auth.py",
        },
    ),
    SemanticDocument(
        entity_id="python.database.connect",
        text=(
            "Entity kind: function\n"
            "Name: connect_database\n"
            "Source code:\n"
            "def connect_database():\n"
            "    return create_database_connection()"
        ),
        metadata={
            "kind": "function",
            "name": "connect_database",
            "file": "database.py",
        },
    ),
]

try:
    # Create an isolated test collection.
    store.ensure_collection()

    # Generate vectors using the real embedding model.
    vectors = provider.embed_documents(
        [document.text for document in documents]
    )

    # Store vectors and source text.
    store.upsert_documents(
        documents=documents,
        vectors=vectors,
        user_id=9999,
        repository_id=9999,
    )

    # Search using a natural-language question.
    query_vector = provider.embed_query(
        "Where are user credentials authenticated?"
    )

    results = store.search(
        query_vector=query_vector,
        user_id=9999,
        repository_id=9999,
        limit=5,
    )

    print("\nSemantic search results:")
    for result in results:
        print(f"\nEntity: {result['entity_id']}")
        print(f"Score: {result['score']:.4f}")
        print(f"Source:\n{result['text']}")

    assert results, "Expected at least one search result"
    assert "login" in results[0]["entity_id"], (
        "Expected the login function to rank first"
    )

    # Verify repository isolation.
    isolated_results = store.search(
        query_vector=query_vector,
        user_id=9999,
        repository_id=1000,
        limit=5,
    )

    assert isolated_results == [], (
        "Search returned results from the wrong repository"
    )

    print("\nPASS: semantic retrieval and repository filtering work.")

finally:
    # Remove the temporary collection, even if an assertion fails.
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.close()
