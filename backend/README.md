# Backend implementation boundary

Planned: FastAPI, SQLite, one bounded assessment runner, typed tool results, and SSE.

Keep API routes thin. Separate orchestration, agent decisions, deterministic tools, persistence, and evaluation. Red and blue receive different contexts. The referee receives the access policy and independent test capabilities.

Start with the target registry and a real lab regression contract before adding LLM-driven planning. No backend service or dependencies are implemented yet.
