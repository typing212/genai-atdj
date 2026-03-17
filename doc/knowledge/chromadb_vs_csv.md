# ChromaDB vs CSV — When a Vector Database Is Necessary

## Answer Summary
ChromaDB is an embedded vector database that stores data alongside dense numerical embeddings and supports semantic similarity search — finding records that are conceptually close to a query, not just exact matches. A CSV with pandas handles structured filtering (style, decade, energy range) perfectly well, but cannot perform semantic search or answer natural-language questions. For AT-DJ, both are used together: the CSV is the editable metadata master, and ChromaDB is the queryable semantic index built from it.

## Key Takeaways
- A CSV covers all **exact/range metadata filtering** (style, orchestra, decade, energy) — sufficient for rule-based tanda planning
- ChromaDB is required for **semantic search**: finding tracks matching a natural-language description like "warm lyrical Di Sarli vals for a mid-energy moment"
- ChromaDB is also required for the **`milonga_knowledge` collection** (orchestra bios, era descriptions) — unstructured text that pandas cannot query
- AT-DJ architecture: CSV = source of truth / editable master; ChromaDB = semantic index built from CSV at ingest time
- ChromaDB supports **combined metadata filter + vector search** in one query — critical for AT-DJ's style/decade pre-filter before semantic re-ranking
- FAISS (alternative) is faster but lacks native metadata filtering; ChromaDB is the better fit for AT-DJ's catalog size (≤10k tracks)
- ChromaDB is **embedded** (in-process, no server) — stored in `data/chroma_db/`; zero infrastructure overhead

## Relevance to AT-DJ Paper
The paper should justify the dual-storage architecture (CSV + ChromaDB) by distinguishing structured metadata retrieval from semantic retrieval — framing ChromaDB as the enabling layer for the RAG Q&A feature and for semantics-aware tanda planning, while the CSV remains the human-editable catalog master.
