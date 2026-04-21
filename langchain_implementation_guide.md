# Building a Hybrid Query System with LangChain

This guide outlines how to technically implement the **Lead Insights & Ticket Intelligence** architecture using the LangChain ecosystem. LangChain provides powerful abstractions that map perfectly to the required ingestion, routing, and query execution flows.

## Core Tech Stack
- **Orchestration**: LangChain (`langchain`, `langchain-core`, `langchain-aws`)
- **LLM & Embeddings**: AWS Bedrock (Claude 3 for generation, Amazon Titan/Nomic for embeddings)
- **Database Engine**: PostgreSQL with `pgvector` (`langchain-postgres` / `langchain-community`)
- **Backend Framework**: FastAPI

---

## 1. Data Ingestion & Vector Storage

To ingest data from the Freshdesk API and prepare it for semantic search, you can utilize LangChain's native `Document` structures and vector store integrations.

**Implementation Structure:**
1. **Load Data**: Pull raw JSON ticket payloads and convert them into LangChain `Document` objects.
2. **Embed**: Use `BedrockEmbeddings` to translate textual descriptions into dense vectors.
3. **Store**: Use LangChain's `PGVector` wrapper to gracefully insert raw text, metadata, and embeddings into the database.

```python
from langchain_core.documents import Document
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import PGVector

# 1. Initialize AWS Bedrock embeddings connection
embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v1")

# 2. Convert raw Freshdesk API payload to Langchain Documents
docs = [
    Document(
        page_content=f"Subject: {ticket['subject']}\n\nDescription: {ticket['description']}",
        metadata={"ticket_id": ticket["id"], "status": ticket["status"]}
    ) 
    for ticket in freshdesk_tickets
]

# 3. Store into PostgreSQL natively using pgvector
vector_store = PGVector.from_documents(
    documents=docs,
    embedding=embeddings,
    connection_string=POSTGRES_URI,
    collection_name="support_tickets"
)
```

## 2. Intent Routing (The Hybrid Engine)

When a user asks a question, the application must decide between deterministic counting (SQL Analytics) or conceptual discovery (Semantic Vector Search). LangChain allows us to build a classification pipeline for this.

**Implementation Procedure:**

```python
from langchain_aws import ChatBedrock
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatBedrock(model_id="anthropic.claude-3-haiku-20240307-v1:0")

route_prompt = PromptTemplate.from_template("""
Classify the following query into exactly one of these two labels:
- 'SQL_ANALYTICS' (if the user is asking for metrics, counts, averages, or concrete status queries).
- 'SEMANTIC_SEARCH' (if the user is asking about thematic topics, generalized workflows, or common issues).

Only return the exact label.
Query: {query}
""")

# Build the LangChain Experimental Evaluation Chain
router_chain = route_prompt | llm | StrOutputParser()

# Usage Example
intent = router_chain.invoke({"query": "How many open tickets do we have?"}) 
# Returns -> "SQL_ANALYTICS"
```

## 3. SQL Analytics Path (with Self-Healing)

For `SQL_ANALYTICS` intents, we generate raw Postgres SQL. LangChain provides native Database tooling.

**Implementation Procedure:**

```python
from langchain.chains import create_sql_query_chain
from langchain_community.utilities import SQLDatabase

# Connect LangChain explicitly to the database to infer schemas automatically
db = SQLDatabase.from_uri(POSTGRES_URI)

# LangChain generates a prompt containing the table schema 'freshdesk_tickets'
sql_chain = create_sql_query_chain(llm, db)

raw_sql = sql_chain.invoke({"question": "Show me the top 5 tickets assigned to Support in the last week."})

# 1. Provide an intercept block here to enforce safety rules (no DELETE/UPDATE keywords).
# 2. Execute via db.run(raw_sql)
```

**Auto-Healing Extension Strategy**:
In a production setting, wrap `db.run()` inside a `try/except` block. Upon encountering a `psycopg2` syntax exception, create a LangChain repair prompt:
*"The query {sql} failed with {error}. Output the correct query using PostgreSQL dialect."*

## 4. Semantic Search Path (RAG Retrieval)

If the intent router evaluates the intent as `SEMANTIC_SEARCH`, LangChain invokes standard RAG abstractions to locate relevant vectors answering conceptual queries.

**Implementation Procedure:**

```python
# Spin up a Retriever interface over the PGVector store created in Step 1
retriever = vector_store.as_retriever(search_kwargs={"k": 7}) # Fetch top 7 most similar

# Retrieve ticket context 
retrieved_docs = retriever.invoke("What are common themes around authentication failures?")

# Build a Synthesis Chain to answer the user gracefully
synthesis_prompt = PromptTemplate.from_template("""
Answer the user's question using ONLY the provided ticket context below.
If you cannot answer based on context, explicitly say so.

Ticket Context: 
{context}

Question: {question}
Answer:
""")

qa_chain = synthesis_prompt | llm | StrOutputParser()
final_markdown_answer = qa_chain.invoke({
    "context": "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs]), 
    "question": "What are common themes around authentication failures?"
})
```

## 5. Exposing via FastAPI

To bring this setup to life, these LangChain sequences (`router_chain`, `sql_chain`, `qa_chain`) are mapped to a `FastAPI` service:

- By structuring chains cleanly, you can use `.ainvoke()` or `astream()` inside FastAPI route handlers.
- FastAPI delivers these LangChain responses directly to an Alpine.js/React frontend where Custom Markdown parsers render `marked.js` dynamically to the client.
