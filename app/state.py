from typing import TypedDict


# MarketState holds everything we know about the business idea.
# total=False means all fields are optional - nodes only update what they produce.
class MarketState(TypedDict, total=False):

    # -------------------------------------------------------
    # Founder intake context (set at graph invocation time)
    # Present only when --intake or founder context is provided; absent otherwise.
    # EPISTEMIC RULE: this field holds founder CLAIMS only.
    # It must never be added to normalized_evidence or cleaned_evidence,
    # and must not count as external empirical evidence.
    # validation_notes must not be passed to persona generation or evaluation prompts.
    # -------------------------------------------------------
    founder_context: dict   # Serialized FounderContext (FounderContext.model_dump())

    # -------------------------------------------------------
    # Preprocessing fields (set by existing nodes)
    # -------------------------------------------------------
    idea: str               # The original business idea from the user
    category: str           # Business category (e.g., "SaaS", "Food & Delivery")
    keywords: list[str]     # Extracted keywords for research
    target_segment: str     # Target customer (e.g., "Working professionals")
    location: str           # Geographic market (e.g., "Pune", "Not specified")
    district: str           # Extracted district if available
    research_type: str      # Decision: "consumer", "location_based", or "general"
    geography_diagnostics: dict  # Precedence and discrepancy tracking between inferred and launch geography
    research_planning_diagnostics: dict  # Summary of research scope, alternatives investigated, and pricing guidance
    persona_count: int      # Target persona count (default 10)
    evaluation_concurrency: int  # Bounded worker concurrency for persona evaluation (default 3)

    # -------------------------------------------------------
    # Research evidence fields (set by the research node)
    # Each field holds a list of structured evidence records.
    # Records are dicts with: source, indicator, value, unit, year, location
    # -------------------------------------------------------
    reddit_evidence: list   # Evidence from Reddit (real posts via Kaggle dataset)
    trends_evidence: list   # Evidence from Google Trends (relative search interest)
    census_evidence: list   # Evidence from Census 2011 (PCA, C-08, C-08A structured evidence)
    plfs_evidence: list     # Evidence from PLFS 2025 (aggregate labour statistics)
    normalized_evidence: list  # Validated common EvidenceRecord dictionaries
    cleaned_evidence: list     # Standardized, deduplicated, atomic EvidenceRecord dictionaries
    cleaning_diagnostics: dict # Diagnostics and counts from cleaning layer
    retrieval_documents: list  # Retrieval-ready document dictionaries (Step 4)
    document_diagnostics: dict # Conversion counts, filtered documents, and diagnostics
    document_chunks: list      # Source-aware chunks ready for embedding/retrieval (Step 5)
    chunking_diagnostics: dict # Chunking counts, strategies, and diagnostics
    chunk_embeddings: list     # Validated chunk embedding records (Step 6)
    embedding_diagnostics: dict # Embedding generation counts, model, dimensions, and issues
    vector_store_diagnostics: dict # ChromaDB storage counts, collection, dimensions, and issues (Step 7)
    vector_store_count: int        # Number of chunks successfully stored in ChromaDB (Step 7)
    chroma_collection_name: str    # Active ChromaDB collection name
    chroma_persist_dir: str        # ChromaDB persistence directory
    evidence_sufficient: bool      # True if empirical research evidence is sufficient to ground personas
    gemini_context: dict           # Gemini-generated startup context & hypotheses when evidence is insufficient
    gemini_context_diagnostics: dict # Diagnostics for Gemini context generation
    personas: list                 # Evidence-grounded synthetic customer personas (Step 9)
    persona_generation_diagnostics: dict # Generation counts, diversity metrics, issues (Step 9)
    persona_evaluations: list      # Simulated customer evaluations and intent records (Step 10)
    persona_evaluation_diagnostics: dict # Evaluation completion counts, score averages, issues (Step 10)
    market_analysis: dict          # Aggregated findings, segment statistics, and evidence validation (Step 11)
    market_analysis_diagnostics: dict # Aggregation diagnostics and audit counts (Step 11)
    market_report: dict            # Final validated structured market validation report (Step 12)
    market_report_diagnostics: dict # Report generation metadata, section counts, diagnostics (Step 12)
    research_questions: list       # Explicit or default market validation research questions
    research_question_answers: list # Structured answers (retrieved_evidence, mixed, or model_knowledge)
    # -------------------------------------------------------
    # Research status fields
    # -------------------------------------------------------
    research_errors: list   # Errors from failed sources (other sources continue)
    research_complete: bool  # True when research node has finished
