# ADR 0001: Use SQLite for Local Storage and Retrieval

- **Status:** Accepted
- **Date:** 2026-09-17

## Context

The tutor assistant will be installed and run locally by one user. It is not currently intended to operate as a centralized service shared by many simultaneous users. Each installation will keep its own student records, lesson transcripts, transcript chunks, and retrieval data. Real student data must remain outside the public repository.

The expected upper-bound workload for one installation is approximately:

- 100 students per year;
- 20 lessons per student;
- 1.25 hours per lesson; and
- one year of retained data.

This produces about 2,000 lessons and 2,500 transcript hours per retained year. The precise number of transcript chunks will depend on the chunking strategy. A broad planning range of 20–80 chunks per lesson would produce roughly 40,000–160,000 chunks.

Retrieval will normally be limited to one explicitly selected student. Searching across multiple students is not a requirement for the first release. The application needs relational storage, exact-word search, semantic search, clear source provenance, and strong safeguards against mixing students' information.

The database choice should meet those requirements without introducing infrastructure solely to demonstrate familiarity with a tool.

## Decision Drivers

- The application is local and single-user.
- Other users should be able to install and run independent copies easily.
- Student data should remain local by default.
- The first release should be understandable and reproducible.
- Retrieval must be scoped to the intended student before relevance is calculated.
- The anticipated dataset is modest when queries are limited to one student.
- The design should permit a vector index or different database to be introduced later if measurements justify it.

## Decision

Use SQLite as the system of record for the first release.

SQLite will store relational application data, including students, lessons, source documents, transcript chunks, and embedding metadata. Foreign keys will preserve an unambiguous path from every transcript chunk to its lesson and student.

The initial retrieval design will use:

1. **SQL prefiltering.** Every retrieval request will require an explicit student scope. SQL will select only chunks belonging to that student, with optional filters such as lesson date or source type.
2. **SQLite FTS5.** Full-text search will find exact words, names, acronyms, and domain-specific phrases.
3. **Embeddings stored as BLOBs.** Each embedding will be stored as a compact float32 byte array alongside the embedding model name, vector dimensions, and other metadata needed to interpret it safely.
4. **Exact vector comparison in Python.** NumPy will calculate cosine similarity between the query embedding and every embedding in the filtered candidate set.
5. **Hybrid ranking.** The application will combine full-text and semantic result rankings in Python rather than treating their incompatible raw scores as interchangeable.
6. **A retrieval interface.** Application code will request results through a small retrieval boundary instead of depending directly on NumPy, FTS5, or a particular vector extension.

The first implementation will not add a vector index. Its performance will be measured with representative data and realistic queries. A SQLite vector extension, a separate local vector index, or PostgreSQL with pgvector will be considered only if those measurements show that exact comparison is too slow.

Cross-student retrieval will remain possible at the data-model level because every chunk retains student provenance. If it is added, callers must select an explicit multi-student scope, tests must verify isolation and provenance, and performance must be evaluated against the larger candidate set.

## Options Considered

### SQLite

SQLite is an embedded relational database stored in a local file. It requires no separate database server and is included with Python.

Advantages:

- closely matches a local, single-user application;
- simple installation, operation, backup, and distribution;
- keeps student data local by default;
- supports transactions, constraints, indexes, foreign keys, and full-text search; and
- is sufficient for the expected relational workload.

Disadvantages:

- does not provide built-in vector search in its standard distribution;
- exact vector comparison must initially occur in application code;
- vector extensions introduce packaging and maturity considerations; and
- it is less suitable than a client-server database for many concurrent writers or a centralized multi-user service.

SQLite is selected because its disadvantages do not conflict with the first release's requirements, while its operational simplicity directly supports them.

### PostgreSQL with pgvector

PostgreSQL is a client-server relational database. pgvector is a PostgreSQL extension, not a separate database; it adds vector columns, distance operators, and approximate vector indexes.

Advantages:

- mature relational database features;
- vector filtering and ranking can occur inside SQL;
- strong support for concurrent users and centralized services; and
- a credible path to indexed vector search at larger scales.

Disadvantages:

- requires a running database service, configuration, credentials, and lifecycle management;
- makes installation and local use more complicated;
- would likely introduce Docker or a native PostgreSQL installation; and
- solves concurrency and centralized-service problems this application does not currently have.

PostgreSQL with pgvector would be appropriate if the application becomes a shared hosted service, needs substantial concurrent access, or outgrows the measured performance of the local retrieval design. It is not selected for the first release.

### Supabase

Supabase is a hosted application platform built around PostgreSQL. It can provide managed PostgreSQL, pgvector, authentication, storage, generated APIs, and other backend services.

Advantages:

- reduces the work of operating a hosted PostgreSQL database;
- provides useful services for a networked, multi-user application; and
- offers a path to centralized access and managed infrastructure.

Disadvantages:

- introduces a cloud dependency and network requirement;
- adds account, deployment, access-control, cost, and data-governance concerns;
- provides capabilities the local first release does not need; and
- makes local-first handling of sensitive student data less direct.

Supabase is not selected because the application does not currently require a hosted backend, shared authentication, or centralized data.

### Dedicated Vector Database

A dedicated vector database specializes in storing, indexing, and searching embeddings.

Advantages:

- designed for large-scale vector search;
- commonly offers approximate nearest-neighbor indexes and vector-oriented filtering; and
- may support distributed or managed deployments.

Disadvantages:

- introduces another service and data store;
- requires relational metadata and vector records to remain synchronized;
- increases deployment, testing, backup, and operational complexity; and
- is unnecessary for searches over one student's modest candidate set.

A dedicated vector database is not selected. It would be reconsidered only if vector-search scale or operational requirements eventually exceed both the SQLite design and a relational solution such as pgvector.

## Consequences

### Positive

- A new user can run the application without operating a database server.
- The default architecture aligns with local ownership and privacy of student data.
- Relational records, full-text indexes, and embeddings can live in one portable database file.
- Exact vector search provides a simple, inspectable correctness baseline.
- Student filtering occurs before semantic ranking, reducing both work and the risk of cross-student retrieval.
- The project demonstrates requirements-driven technology selection rather than infrastructure for its own sake.

### Negative

- The application must serialize and deserialize embedding arrays.
- Python is responsible for vector scoring and hybrid result fusion.
- Exact comparison may become slow for broad or cross-student searches.
- SQLite vector extensions cannot be assumed to be installed everywhere and will require separate evaluation if adopted.
- The project will not demonstrate PostgreSQL, pgvector, Docker-based database operation, or managed cloud infrastructure in its first release.

### Risks and Mitigations

- **Risk: semantic retrieval is slower than expected.** Benchmark latency using representative chunk counts and query patterns. Add an index only after identifying an explicit performance target and measuring a failure to meet it.
- **Risk: records from different students are mixed.** Require an explicit retrieval scope, enforce chunk-to-student provenance through relational constraints, and test that results never escape the requested scope.
- **Risk: embeddings become uninterpretable after changing models.** Store the embedding model, dimensions, and relevant generation metadata with each embedding, and prevent comparisons between incompatible embeddings.
- **Risk: the retrieval implementation becomes coupled to SQLite or NumPy.** Keep storage and ranking details behind a small retrieval interface whose results include source provenance.
- **Risk: the local database file is lost or copied insecurely.** Document backup, recovery, file-location, and sensitive-data handling practices before using real student data.

## Revisit This Decision When

Re-evaluate the database or vector-search implementation if one or more of the following becomes true:

- representative benchmarks fail an agreed retrieval-latency target;
- routine queries must search many or all students;
- the application becomes a centralized service used concurrently by multiple people;
- multiple processes or machines must write to the same database;
- centralized authentication, remote access, or managed backups become requirements; or
- operating a vector index outside the relational database creates unacceptable consistency or maintenance costs.

These triggers permit an incremental change rather than requiring a speculative migration now. Depending on the measured problem, the next step could be a SQLite vector extension, a local vector index, PostgreSQL with pgvector, or a managed PostgreSQL platform.

## Validation Plan

Before revisiting the decision, the project will:

- test relational constraints and student isolation;
- test embedding serialization and compatibility checks;
- evaluate full-text, semantic, and hybrid retrieval quality;
- benchmark exact vector search with representative per-student and full-dataset candidate counts; and
- record the dataset size, hardware, query scope, and latency thresholds used in the benchmark.
