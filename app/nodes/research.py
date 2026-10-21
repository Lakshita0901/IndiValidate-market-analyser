"""
research.py
-----------
The research node for Phase 1 of IndiValidate.

Called AFTER the research_decision node.
Collects real evidence from four independent sources:

    1. Reddit (Kaggle dataset) — historical dataset keyword search
    2. Google Trends           — real relative search interest via pytrends
    3. Census 2011             — real aggregate data from local official Census datasets (PCA, C-08, C-08A)
    4. PLFS 2025               — real labour data from official CSV files

Design principles:
    - Each source is called independently
    - If one source fails, the others continue
    - Errors are stored in research_errors (NOT as fake data)
    - No LLM is called here — this node is deterministic
    - research_complete is set to True when this node finishes

State fields consumed:
    state["idea"]            - the original business idea
    state["keywords"]        - extracted keywords (from keywords node)
    state["target_segment"]  - target customer (from target node)
    state["location"]        - geographic market (from location node)
    state["district"]        - extracted district if available
    state["research_type"]   - consumer/location_based/general (from research_decision)
"""

from langchain_core.tools import BaseTool
from app.state import MarketState
from app.tools.reddit_tool import run_reddit_search
from app.tools.trends_tool import run_trends_search
from app.tools.census_tool import run_census_search
from app.tools.plfs_tool import run_plfs_search
from app.schemas.normalizer import normalize_all_evidence
from app.schemas.cleaner import clean_evidence
from app.rag.document_builder import build_retrieval_documents
from app.rag.chunker import chunk_documents
from app.rag.embeddings import generate_chunk_embeddings
from app.rag.vector_store import (
    DEFAULT_COLLECTION_NAME,
    ChromaVectorStore,
    get_collection_name_for_model,
    store_chunk_embeddings,
)





def _invoke_tool(tool_obj, kwargs: dict) -> dict:
    """
    Safely invoke a tool:
    - If it's a LangChain BaseTool, uses canonical tool.invoke(kwargs) in production.
    - If it's a mock or plain callable (e.g. during testing/patching), calls it directly with kwargs.
    """
    if isinstance(tool_obj, BaseTool):
        return tool_obj.invoke(kwargs)
    if callable(tool_obj):
        return tool_obj(**kwargs)
    if hasattr(tool_obj, "func") and callable(tool_obj.func):
        return tool_obj.func(**kwargs)
    if hasattr(tool_obj, "invoke") and callable(tool_obj.invoke):
        return tool_obj.invoke(kwargs)
    raise TypeError(f"Cannot invoke tool object of type {type(tool_obj)}")


def run_research(state: MarketState) -> dict:
    """
    The main research node function.

    Calls all four evidence sources in sequence.
    Each source failure is caught independently so others can continue.

    Returns updated state fields:
        reddit_evidence   : list of Reddit historical dataset records
        trends_evidence   : list of Google Trends records (one per keyword)
        census_evidence   : list containing structured Census 2011 evidence
        plfs_evidence     : list of PLFS 2025 labour/employment records
        research_errors   : list of error records (one per failed source)
        research_complete : True (always set, even if some sources failed)
    """
    print("\n>>> STARTING RESEARCH")

    if state.get("research_complete") and state.get("cleaned_evidence") is not None:
        print("    Reusing cached empirical research evidence from prior execution.")
        return {
            "reddit_evidence": state.get("reddit_evidence", []),
            "trends_evidence": state.get("trends_evidence", []),
            "census_evidence": state.get("census_evidence", []),
            "plfs_evidence": state.get("plfs_evidence", []),
            "normalized_evidence": state.get("normalized_evidence", []),
            "cleaned_evidence": state.get("cleaned_evidence", []),
            "cleaning_diagnostics": state.get("cleaning_diagnostics", {}),
            "retrieval_documents": state.get("retrieval_documents", []),
            "document_diagnostics": state.get("document_diagnostics", {}),
            "document_chunks": state.get("document_chunks", []),
            "chunking_diagnostics": state.get("chunking_diagnostics", {}),
            "chunk_embeddings": state.get("chunk_embeddings", []),
            "embedding_diagnostics": state.get("embedding_diagnostics", {}),
            "vector_store_diagnostics": state.get("vector_store_diagnostics", {}),
            "vector_store_count": state.get("vector_store_count", 0),
            "chroma_collection_name": state.get("chroma_collection_name", "market_evidence_chunks"),
            "chroma_persist_dir": state.get("chroma_persist_dir", "data/chroma"),
            "geography_diagnostics": state.get("geography_diagnostics", {}),
            "research_planning_diagnostics": state.get("research_planning_diagnostics", {}),
            "research_errors": state.get("research_errors", []),
            "research_complete": True,
        }

    # Read from state (use .get() for safety since total=False)
    idea = state.get("idea", "")
    keywords = state.get("keywords", [])
    target = state.get("target_segment", "")
    location = state.get("location", "Not specified")
    district = state.get("district", None)
    founder_ctx = state.get("founder_context") or {}

    # Launch geography precedence and discrepancy tracking
    launch_geo = founder_ctx.get("launch_geography")
    geographic_scope = founder_ctx.get("geographic_scope")
    inferred_location = location
    has_geo_discrepancy = False
    geo_discrepancy_msg = None

    if launch_geo and str(launch_geo).strip():
        clean_launch_geo = str(launch_geo).strip()
        if inferred_location and inferred_location.lower() not in ("not specified", ""):
            if inferred_location.lower() != clean_launch_geo.lower():
                has_geo_discrepancy = True
                geo_discrepancy_msg = (
                    f"Discrepancy: Inferred location '{inferred_location}' conflicts with "
                    f"explicit founder launch geography '{clean_launch_geo}'. "
                    f"Founder launch geography takes precedence."
                )
        location = clean_launch_geo

    geography_diagnostics = state.get("geography_diagnostics") or {
        "inferred_location": inferred_location,
        "launch_geography": launch_geo,
        "active_location": location,
        "geographic_scope": geographic_scope,
        "has_discrepancy": has_geo_discrepancy,
    }
    if geo_discrepancy_msg and "discrepancy_message" not in geography_diagnostics:
        geography_diagnostics["discrepancy_message"] = geo_discrepancy_msg
        geography_diagnostics["has_discrepancy"] = True

    # Pricing guidance for research planning
    pricing_model = founder_ctx.get("pricing_model")
    expected_price = founder_ctx.get("expected_price")
    pricing_guidance = None
    if pricing_model or expected_price:
        pricing_guidance = {
            "pricing_model": pricing_model,
            "expected_price": expected_price,
            "guidance_note": (
                "Pricing information guides research planning and affordability framing; "
                "never treated as empirical willingness-to-pay estimate."
            ),
        }

    # Competitor and alternative investigation in Reddit
    reddit_keywords = list(keywords)
    known_alts = founder_ctx.get("known_alternatives") or []
    for alt in known_alts:
        if alt and str(alt).strip():
            clean_alt = str(alt).strip()
            if clean_alt.lower() not in [k.lower() for k in reddit_keywords]:
                reddit_keywords.append(clean_alt)

    research_planning_diagnostics = {
        "geography": geography_diagnostics,
        "known_alternatives_investigated": known_alts,
        "pricing_guidance": pricing_guidance,
        "external_evidence_isolation_verified": True,
    }

    # Collect errors from all sources
    research_errors = []

    # =========================================================
    # SOURCE 1: REDDIT (Kaggle historical dataset)
    # =========================================================
    print("\n>>> REDDIT RESEARCH")

    reddit_evidence = []
    try:
        # Pass both the idea query and extracted keywords (including alternatives)
        # The tool uses keywords for matching, query for context
        reddit_results = run_reddit_search(
            query=idea,
            keywords=reddit_keywords
        )

        for record in reddit_results:
            status = record.get("status", "")
            if status in ("error", "no_results"):
                research_errors.append({
                    "source": "Reddit (Kaggle dataset)",
                    "error": record.get("error", "Unknown Reddit error")
                })
            else:
                reddit_evidence.append(record)

        if reddit_evidence:
            print(f"    Found: {len(reddit_evidence)} relevant records")
        else:
            no_res_msg = ""
            for r in reddit_results:
                if r.get("status") == "no_results" and r.get("error"):
                    no_res_msg = f" ({r.get('error')})"
                    break
            print(f"    Found: 0 records{no_res_msg or ' (see Research Errors below)'}")

    except Exception as e:
        research_errors.append({
            "source": "Reddit (Kaggle dataset)",
            "error": f"Unexpected Reddit tool error: {str(e)}"
        })
        print(f"    Error: {e}")

    # =========================================================
    # SOURCE 2: GOOGLE TRENDS
    # =========================================================
    print("\n>>> GOOGLE TRENDS")

    trends_evidence = []
    try:
        keywords_for_trends = keywords if keywords else [idea]
        trends_results = run_trends_search(keywords_for_trends, location)

        for record in trends_results:
            status = record.get("status", "")
            if status == "error":
                research_errors.append({
                    "source": "Google Trends",
                    "keyword": record.get("keyword", ""),
                    "error": record.get("error", "Unknown Trends error")
                })
            elif status == "no_data":
                research_errors.append({
                    "source": "Google Trends",
                    "keyword": record.get("keyword", ""),
                    "error": record.get("error", "No data for this keyword")
                })
            else:
                trends_evidence.append(record)

        if trends_evidence:
            print(f"    Found: {len(trends_evidence)} keyword signals")
        else:
            print("    Found: 0 signals (see Research Errors below)")

    except Exception as e:
        research_errors.append({
            "source": "Google Trends",
            "error": f"Unexpected Trends tool error: {str(e)}"
        })
        print(f"    Error: {e}")

    # =========================================================
    # SOURCE 3: CENSUS 2011 (Local official datasets: PCA, C-08, C-08A)
    # =========================================================
    print("\n>>> CENSUS RESEARCH")

    census_evidence = []
    try:
        census_result = _invoke_tool(
            run_census_search,
            {"location": location, "district": district or ""}
        )

        if census_result.get("status") == "error":
            err_msg = census_result.get("error", "Unknown Census error")
            research_errors.append({
                "source": "Census 2011",
                "error": err_msg
            })
            print("Census:")
            print(f"  status: error")
            print(f"  error: {err_msg}")
        else:
            census_evidence.append(census_result)
            geo = census_result.get("geography", {})
            pca_data = census_result.get("pca", {})
            c08_data = census_result.get("education", {})
            c08a_data = census_result.get("higher_education", {})

            pop = pca_data.get("population", {}).get("total", "N/A")
            hh = pca_data.get("households", "N/A")
            lit_pct = pca_data.get("literacy", {}).get("crude_literacy_rate_percent", "N/A")

            c08_lit = c08_data.get("summary", {}).get("literates", {}).get("persons", "N/A")
            c08_grad = c08_data.get("summary", {}).get("levels", {}).get("graduate_and_above", {}).get("persons", "N/A")
            c08_tru = c08_data.get("tru", "Total")
            c08_note = " (state fallback)" if c08_data.get("is_state_fallback") else ""

            eng = c08a_data.get("summary", {}).get("disciplines", {}).get("engineering_and_technology", {}).get("persons", "N/A")
            med = c08a_data.get("summary", {}).get("disciplines", {}).get("medicine", {}).get("persons", "N/A")
            teach = c08a_data.get("summary", {}).get("disciplines", {}).get("teaching", {}).get("persons", "N/A")

            print("Census:")
            print(f"  status: success")
            print(f"  state: {geo.get('state', 'N/A')}")
            print(f"  district: {geo.get('district') or 'None (State-level)'}")
            pop_str = f"{pop:,}" if isinstance(pop, int) else str(pop)
            hh_str = f"{hh:,}" if isinstance(hh, int) else str(hh)
            print(f"  PCA: Pop={pop_str}, Households={hh_str}, Literacy={lit_pct}%")
            c08_lit_str = f"{c08_lit:,}" if isinstance(c08_lit, int) else str(c08_lit)
            c08_grad_str = f"{c08_grad:,}" if isinstance(c08_grad, int) else str(c08_grad)
            print(f"  C-08: Literates={c08_lit_str}, Graduates={c08_grad_str} [{c08_tru}]{c08_note}")
            eng_str = f"{eng:,}" if isinstance(eng, int) else str(eng)
            med_str = f"{med:,}" if isinstance(med, int) else str(med)
            teach_str = f"{teach:,}" if isinstance(teach, int) else str(teach)
            print(f"  C-08A: Engineering={eng_str}, Medicine={med_str}, Teaching={teach_str}")

    except Exception as e:
        research_errors.append({
            "source": "Census 2011",
            "error": f"Unexpected Census tool error: {str(e)}"
        })
        print(f"    Error: {e}")

    # =========================================================
    # SOURCE 4: PLFS 2025
    # =========================================================
    print("\n>>> PLFS RESEARCH")

    plfs_evidence = []
    try:
        plfs_result = _invoke_tool(
            run_plfs_search,
            {
                "location": location,
                "district": district or "",
                "target_segment": target,
            }
        )

        if plfs_result.get("status") == "error":
            err_msg = plfs_result.get("error", "Unknown PLFS error")
            research_errors.append({
                "source": "PLFS 2025",
                "error": err_msg
            })
            print("PLFS 2025:")
            print(f"  status: error")
            print(f"  error: {err_msg}")
        else:
            plfs_evidence.append(plfs_result)
            geo = plfs_result.get("geography", {})
            labour = plfs_result.get("labour_indicators", {}).get("usual_status_ps_plus_ss", {})
            earn = plfs_result.get("earnings", {})
            edu = plfs_result.get("education", {})

            lfpr = labour.get("lfpr_percent", "N/A")
            wpr = labour.get("wpr_percent", "N/A")
            ur = labour.get("unemployment_rate_percent", "N/A")

            sal = earn.get("regular_salaried", {}).get("avg_monthly_salary_inr", "N/A")
            sal_str = f"INR {sal:,.2f}" if isinstance(sal, (int, float)) else str(sal)
            self_e = earn.get("self_employed", {}).get("avg_monthly_earnings_inr", "N/A")
            self_str = f"INR {self_e:,.2f}" if isinstance(self_e, (int, float)) else str(self_e)

            grad_pct = edu.get("graduate_and_above_percent", "N/A")

            print("PLFS 2025:")
            print(f"  status: success")
            print(f"  state: {geo.get('state', 'N/A')}")
            print(f"  district: {geo.get('district') or 'None (State-level)'}")
            print(f"  LFPR: {lfpr}%, WPR: {wpr}%, UR: {ur}% (Age 15+, Usual Status)")
            print(f"  Earnings: Avg Salary={sal_str}/mo, Avg Self-Employed={self_str}/mo")
            print(f"  Education: Graduate and Above={grad_pct}%")

    except Exception as e:
        research_errors.append({
            "source": "PLFS 2025",
            "error": f"Unexpected PLFS tool error: {str(e)}"
        })
        print(f"    Error: {e}")

    # =========================================================
    # SUMMARY
    # =========================================================
    print("\n>>> RESEARCH COMPLETE")
    print(f"    Reddit:  {len(reddit_evidence)} records")
    print(f"    Trends:  {len(trends_evidence)} signals")
    print(f"    Census:  {'1 structured evidence record' if census_evidence else '0 records'}")
    print(f"    PLFS:    {'1 structured evidence record' if plfs_evidence else '0 records'}")
    if research_errors:
        print(f"    Errors:  {len(research_errors)} source error(s)")

    # Normalize all collected raw evidence into validated common schema
    normalized_records = normalize_all_evidence(
        reddit_evidence=reddit_evidence,
        trends_evidence=trends_evidence,
        census_evidence=census_evidence,
        plfs_evidence=plfs_evidence,
    )
    normalized_evidence = [rec.model_dump() for rec in normalized_records]
    print(f"    Normalized: {len(normalized_evidence)} common evidence records")

    # Clean, standardize, validate, and decompose atomic metrics
    cleaned_records, cleaning_diagnostics = clean_evidence(
        normalized_records,
        query=idea,
        keywords=keywords,
    )
    cleaned_evidence = [rec.model_dump() for rec in cleaned_records]
    print(f"    Cleaned:    {len(cleaned_evidence)} standardized evidence records (Deduplicated: {cleaning_diagnostics['duplicates_removed_count']}, Decomposed: {cleaning_diagnostics['atomic_metrics_expanded_count']})")

    # Build retrieval-ready documents from cleaned evidence (Step 4)
    retrieval_docs, document_diagnostics = build_retrieval_documents(cleaned_records)
    retrieval_documents = [doc.model_dump() for doc in retrieval_docs]
    print(f"    Documents:  {len(retrieval_documents)} retrieval-ready documents (Excluded irrelevant: {document_diagnostics['excluded_irrelevant_count']})")

    # Source-aware chunking for future embedding and retrieval (Step 5)
    chunks, chunking_diagnostics = chunk_documents(retrieval_docs)
    document_chunks = [c.model_dump() for c in chunks]
    print(f"    Chunks:     {len(document_chunks)} source-aware chunks (Eligible docs: {chunking_diagnostics['eligible_documents_count']}, Skipped: {chunking_diagnostics['skipped_ineligible_count']})")

    # Generate and validate embeddings (Step 6)
    embedding_provider = state.get("embedding_provider")
    generate_embeddings_flag = state.get("generate_embeddings", True)

    chunk_embeddings = []
    embedding_diagnostics = {
        "total_chunks_received": len(chunks),
        "eligible_chunks_count": 0,
        "embeddings_generated_count": 0,
        "failed_chunks_count": 0,
        "embedding_model": None,
        "embedding_dimensions": None,
        "batches_processed": 0,
        "issues": [],
    }

    if generate_embeddings_flag and chunks:
        import os
        has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        if embedding_provider is None and not has_key:
            embedding_diagnostics["issues"].append(
                "Skipped live embedding generation: Google API key not found in environment."
            )
            print("    Embeddings: Skipped (no API key configured)")
        else:
            try:
                emb_records, emb_diag = generate_chunk_embeddings(chunks, provider=embedding_provider)
                chunk_embeddings = [r.model_dump() for r in emb_records]
                embedding_diagnostics = emb_diag
                dims_str = f" ({emb_diag['embedding_dimensions']} dims)" if emb_diag.get("embedding_dimensions") else ""
                print(f"    Embeddings: {len(chunk_embeddings)} validated vectors{dims_str} [Model: {emb_diag.get('embedding_model')}]")
            except Exception as e:
                embedding_diagnostics["issues"].append(f"Unexpected embedding generation error: {e}")
                print(f"    Embeddings Error: {e}")

    # -------------------------------------------------------------
    # Step 7: Persistent ChromaDB Vector Store & Indexing
    # -------------------------------------------------------------
    store_embeddings_flag = state.get("store_embeddings", True)
    vector_store_instance = state.get("vector_store")
    custom_persist_dir = state.get("chroma_persist_dir")
    custom_col_name = state.get("chroma_collection_name")

    # Determine model and dimensions from generated embeddings
    model_name = None
    dims = None
    if chunk_embeddings:
        first_chunk = chunk_embeddings[0]
        if hasattr(first_chunk, "embedding_model"):
            model_name = first_chunk.embedding_model
            dims = first_chunk.embedding_dimensions
        elif isinstance(first_chunk, dict):
            model_name = first_chunk.get("embedding_model")
            dims = first_chunk.get("embedding_dimensions")

    # Isolate collection by model & dimensions if not explicitly overridden
    target_col_name = custom_col_name or get_collection_name_for_model(
        base_name=DEFAULT_COLLECTION_NAME,
        embedding_model=model_name,
        embedding_dimensions=dims,
    )

    vector_store_diagnostics = {
        "total_records_received": len(chunk_embeddings),
        "successfully_stored_count": 0,
        "failed_records_count": 0,
        "collection_name": target_col_name,
        "persistence_directory": str(custom_persist_dir or "data/chroma"),
        "total_collection_count": 0,
        "embedding_model": model_name,
        "embedding_dimensions": dims,
        "issues": [],
    }
    vector_store_count = 0

    if store_embeddings_flag and chunk_embeddings:
        try:
            vs = vector_store_instance or ChromaVectorStore(
                persist_directory=custom_persist_dir,
                collection_name=target_col_name,
            )
            count_stored, vs_diag = vs.store_embeddings(chunk_embeddings)
            vector_store_diagnostics = vs_diag
            vector_store_count = count_stored
            print(f"    Vector Store: {vector_store_count} chunks persisted to '{vs_diag.get('collection_name')}' (Total in collection: {vs_diag.get('total_collection_count')})")
        except Exception as e:
            vector_store_diagnostics["issues"].append(f"Vector store persistence error: {e}")
            print(f"    Vector Store Error: {e}")

    return {
        "reddit_evidence": reddit_evidence,
        "trends_evidence": trends_evidence,
        "census_evidence": census_evidence,
        "plfs_evidence": plfs_evidence,
        "normalized_evidence": normalized_evidence,
        "cleaned_evidence": cleaned_evidence,
        "cleaning_diagnostics": cleaning_diagnostics,
        "retrieval_documents": retrieval_documents,
        "document_diagnostics": document_diagnostics,
        "document_chunks": document_chunks,
        "chunking_diagnostics": chunking_diagnostics,
        "chunk_embeddings": chunk_embeddings,
        "embedding_diagnostics": embedding_diagnostics,
        "vector_store_diagnostics": vector_store_diagnostics,
        "vector_store_count": vector_store_count,
        "chroma_collection_name": target_col_name,
        "chroma_persist_dir": str(custom_persist_dir or "data/chroma"),
        "geography_diagnostics": geography_diagnostics,
        "research_planning_diagnostics": research_planning_diagnostics,
        "research_errors": research_errors,
        "research_complete": True
    }



