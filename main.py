from dotenv import load_dotenv

# Load .env before importing the graph (required for API keys)
load_dotenv()

from app.graph import build_graph


# ================================================================
# Display helpers
# ================================================================

def _sep(title: str = ""):
    if title:
        print(f"\n{'='*50}")
        print(f"  {title}")
        print('='*50)
    else:
        print('='*50)


def _print_reddit_evidence(evidence: list):
    if not evidence:
        return
    print(f"\n  Reddit Evidence ({len(evidence)} records from Kaggle dataset):")
    for post in evidence:
        title = post.get("title", "")[:70]
        sub = post.get("subreddit", "?")
        score = post.get("score", "N/A")
        matched = post.get("keywords_matched", [])
        print(f"    [{sub}] {title}")
        print(f"      Score: {score} | Matched keywords: {matched}")
        text = post.get("text", "").replace("\n", " ")[:100]
        if text:
            print(f"      Preview: {text}...")
        url = post.get("url", "")
        if url:
            print(f"      URL: {url}")
        print()


def _print_trends_evidence(evidence: list):
    if not evidence:
        return
    print(f"\n  Google Trends ({len(evidence)} keyword signals):")
    for item in evidence:
        keyword = item.get("keyword", "")
        direction = item.get("trend_direction", "unknown")
        latest = item.get("latest_value", "N/A")
        avg = item.get("average_value", "N/A")
        geo = item.get("geo", "IN")
        print(f"    '{keyword}' | Geo: {geo}")
        print(f"      Relative interest: latest={latest}/100, avg={avg}/100 | Trend: {direction}")
        print()


def _print_census_evidence(evidence: list):
    if not evidence:
        return
    print(f"\n  Census 2011 Evidence (Official Government Datasets):")
    for record in evidence:
        geo = record.get("geography", {})
        pca = record.get("pca", {})
        c08 = record.get("education", {})
        c08a = record.get("higher_education", {})

        state_name = geo.get("state", "N/A")
        dist_name = geo.get("district") or "None (State-level aggregate)"
        level = geo.get("level", "")
        tru = geo.get("tru", "Total")
        print(f"    Geography: {dist_name}, {state_name} [Level: {level}, Residence: {tru}]")

        # PCA section
        pop = pca.get("population", {})
        tot_p = pop.get("total", "N/A")
        hh = pca.get("households", "N/A")
        lit = pca.get("literacy", {})
        workers = pca.get("workers", {})
        w_cats = workers.get("categories", {})

        tot_p_str = f"{tot_p:,}" if isinstance(tot_p, int) else str(tot_p)
        hh_str = f"{hh:,}" if isinstance(hh, int) else str(hh)
        print(f"\n    [PCA 2011 - Demographics & Workers]")
        print(f"      Population: {tot_p_str} (Male: {pop.get('male', 0):,}, Female: {pop.get('female', 0):,})")
        print(f"      Sex Ratio: {pop.get('sex_ratio_females_per_1000_males', 'N/A')} females/1000 males | Households: {hh_str}")
        print(f"      Literacy: {lit.get('literate_total', 0):,} ({lit.get('crude_literacy_rate_percent', 'N/A')}%)")
        print(f"      Total Workers: {workers.get('total_workers', 0):,} ({workers.get('work_participation_rate_percent', 'N/A')}% participation)")
        print(f"      Worker Categories:")
        print(f"        - Cultivators: {w_cats.get('cultivators', {}).get('count', 0):,} ({w_cats.get('cultivators', {}).get('share_of_workers_percent', 0)}%)")
        print(f"        - Agricultural Labourers: {w_cats.get('agricultural_labourers', {}).get('count', 0):,} ({w_cats.get('agricultural_labourers', {}).get('share_of_workers_percent', 0)}%)")
        print(f"        - Household Industry: {w_cats.get('household_industry', {}).get('count', 0):,} ({w_cats.get('household_industry', {}).get('share_of_workers_percent', 0)}%)")
        print(f"        - Other Workers: {w_cats.get('other_workers', {}).get('count', 0):,} ({w_cats.get('other_workers', {}).get('share_of_workers_percent', 0)}%)")

        # C-08 section
        c08_sum = c08.get("summary", {})
        c08_lev = c08_sum.get("levels", {})
        c08_met = c08_sum.get("metrics", {})
        fallback_str = " (state fallback)" if c08.get("is_state_fallback") else ""
        print(f"\n    [Table C-08 - Educational Attainment]{fallback_str}")
        print(f"      Literates: {c08_sum.get('literates', {}).get('persons', 0):,} | Illiterates: {c08_sum.get('illiterates', {}).get('persons', 0):,}")
        print(f"      Graduate & Above: {c08_lev.get('graduate_and_above', {}).get('persons', 0):,} ({c08_met.get('graduate_share_percent', 0)}%)")
        print(f"      Higher Secondary: {c08_lev.get('higher_secondary_intermediate', {}).get('persons', 0):,}")
        print(f"      Matric/Secondary: {c08_lev.get('matric_secondary', {}).get('persons', 0):,}")
        print(f"      Technical Diploma: {c08_lev.get('technical_diploma', {}).get('persons', 0):,}")

        # C-08A section
        c08a_sum = c08a.get("summary", {})
        c08a_disc = c08a_sum.get("disciplines", {})
        c08a_met = c08a_sum.get("metrics", {})
        print(f"\n    [Table C-08A - Higher Education Disciplines]{fallback_str}")
        print(f"      Total Graduates & Above (15+): {c08a_sum.get('total_graduates_and_above', {}).get('persons', 0):,}")
        print(f"      Engineering & Technology: {c08a_disc.get('engineering_and_technology', {}).get('persons', 0):,} ({c08a_met.get('engineering_share_of_graduates_percent', 0)}% of grads)")
        print(f"      Medicine: {c08a_disc.get('medicine', {}).get('persons', 0):,} ({c08a_met.get('medicine_share_of_graduates_percent', 0)}% of grads)")
        print(f"      Teaching: {c08a_disc.get('teaching', {}).get('persons', 0):,} ({c08a_met.get('teaching_share_of_graduates_percent', 0)}% of grads)")
        print(f"      Agriculture & Dairying: {c08a_disc.get('agriculture_and_dairying', {}).get('persons', 0):,}")
        print(f"      Veterinary: {c08a_disc.get('veterinary', {}).get('persons', 0):,}")
        print(f"      Non-Technical Graduate Degrees: {c08a_disc.get('non_technical_graduate', {}).get('persons', 0):,}")
        print()


def _print_plfs_evidence(evidence: list):
    if not evidence:
        return
    print(f"\n  PLFS 2025 Evidence (Official Government Microdata):")
    for record in evidence:
        geo = record.get("geography", {})
        meta = record.get("sample_metadata", {})
        labour = record.get("labour_indicators", {})
        us = labour.get("usual_status_ps_plus_ss", {})
        ps = labour.get("principal_status_ps", {})
        earn = record.get("earnings", {})
        edu = record.get("education", {})
        emp = record.get("employment", {})
        ocu = record.get("occupation", [])
        ind = record.get("industry", [])
        hh = record.get("household", {})

        state_name = geo.get("state", "N/A")
        dist_name = geo.get("district") or "None (State aggregate)"
        level = geo.get("level", "")
        sector = geo.get("sector", "Total")
        print(f"    Geography: {dist_name}, {state_name} [Level: {level}, Sector: {sector}]")
        print(f"      Survey Sample: {meta.get('sample_persons_total', 0):,} persons ({meta.get('sample_persons_age_15_plus', 0):,} Age 15+)")
        print(f"      Estimated Population: {meta.get('estimated_population_total', 0):,} (Age 15+: {meta.get('estimated_population_age_15_plus', 0):,})")

        print(f"\n    [Labour Force Indicators - Age 15+ Standard]")
        print(f"      Usual Status (ps+ss) headline: LFPR={us.get('lfpr_percent', 'N/A')}%, WPR={us.get('wpr_percent', 'N/A')}%, Unemployment Rate={us.get('unemployment_rate_percent', 'N/A')}%")
        print(f"      Principal Status (ps) major:   LFPR={ps.get('lfpr_percent', 'N/A')}%, WPR={ps.get('wpr_percent', 'N/A')}%, Unemployment Rate={ps.get('unemployment_rate_percent', 'N/A')}%")

        reg = earn.get("regular_salaried", {})
        se = earn.get("self_employed", {})
        sal_avg = reg.get("avg_monthly_salary_inr", 0)
        sal_med = reg.get("median_monthly_salary_inr", 0)
        se_avg = se.get("avg_monthly_earnings_inr", 0)
        se_med = se.get("median_monthly_earnings_inr", 0)
        print(f"\n    [Monthly Earnings (Weighted Averages)]")
        print(f"      Regular Salaried:    Avg=INR {sal_avg:,.2f}/mo (Median=INR {sal_med:,.2f}, N={reg.get('sample_size', 0)})")
        print(f"      Self-Employed Gross: Avg=INR {se_avg:,.2f}/mo (Median=INR {se_med:,.2f}, N={se.get('sample_size', 0)})")

        print(f"\n    [Education Attainment - Age 15+]")
        print(f"      Graduate & Above: {edu.get('graduate_and_above_percent', 'N/A')}% | Secondary & Above: {edu.get('secondary_and_above_percent', 'N/A')}% | Not Literate: {edu.get('not_literate_percent', 'N/A')}%")

        if ocu:
            print(f"\n    [Top Occupation Groups (NCO-2015)]")
            for o in ocu[:4]:
                print(f"      - {o.get('occupation_group')}: {o.get('weighted_share_percent')}%")

        if ind:
            print(f"\n    [Top Industry Divisions (NIC-2008)]")
            for i in ind[:4]:
                print(f"      - {i.get('industry_division')}: {i.get('weighted_share_percent')}%")

        if hh and hh.get("status") == "available":
            hce = hh.get("avg_monthly_consumer_expenditure_inr")
            hce_str = f"INR {hce:,.2f}" if hce else "N/A"
            print(f"\n    [Household Context]")
            print(f"      Avg Household Size: {hh.get('avg_household_size')} persons | Avg Monthly Consumer Exp: {hce_str}")
        print()


def _print_research_errors_section(errors: list):
    """Print a clean error summary grouped by source."""
    _sep("RESEARCH ERRORS")

    sources = ["Reddit (Kaggle dataset)", "Google Trends", "Census 2011", "PLFS 2025"]
    errors_by_source = {s: [] for s in sources}

    for err in errors:
        src = err.get("source", "Unknown")
        errors_by_source.setdefault(src, []).append(err)

    any_errors = False
    for source in sources:
        errs = errors_by_source.get(source, [])
        if errs:
            any_errors = True
            for e in errs:
                msg = e.get("error", "")[:120]
                print(f"  [{source}] {msg}")
                # Show PLFS setup instructions (first few lines only)
                if e.get("how_to_fix"):
                    for line in e["how_to_fix"][:6]:
                        print(f"    {line}")
        else:
            print(f"  [{source}] none")

    if not any_errors:
        print("  All sources returned data successfully.")


def _print_normalized_evidence(evidence: list):
    if not evidence:
        return
    _sep("COMMON EVIDENCE SCHEMA (NORMALIZED)")
    print(f"\n  Total Normalized Records: {len(evidence)}")
    by_source = {}
    by_type = {}
    for rec in evidence:
        s = rec.get("source", "unknown")
        s = getattr(s, "value", str(s))
        t = rec.get("evidence_type", "unknown")
        t = getattr(t, "value", str(t))
        by_source[s] = by_source.get(s, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1

    print("  Breakdown by Source:")
    for s, c in sorted(by_source.items()):
        print(f"    - {s}: {c} records")
    print("  Breakdown by Evidence Type:")
    for t, c in sorted(by_type.items()):
        print(f"    - {t}: {c} records")

    print("\n  Sample Normalized Observations:")
    for rec in evidence[:4]:
        eid = rec.get("evidence_id", "")
        src = rec.get("source", "")
        src = getattr(src, "value", str(src))
        etype = rec.get("evidence_type", "")
        etype = getattr(etype, "value", str(etype))
        title = rec.get("title", "")
        val = rec.get("value")
        unit = rec.get("unit") or ""
        val_str = f" [Value: {val} {unit}]" if val is not None else ""
        print(f"    [{src} | {etype}] {title}{val_str}")
        print(f"      ID: {eid} | Time: {rec.get('time_period') or 'N/A'}")


def _print_cleaned_evidence(evidence: list, diagnostics: dict):
    if not evidence:
        return
    _sep("STANDARDIZED & CLEANED EVIDENCE (STEP 3)")
    print(f"\n  Total Cleaned Records: {len(evidence)}")
    if diagnostics:
        print("  Diagnostics:")
        print(f"    - Duplicates removed: {diagnostics.get('duplicates_removed_count', 0)}")
        print(f"    - Atomic metrics expanded: {diagnostics.get('atomic_metrics_expanded_count', 0)}")
        print(f"    - Valid numeric checks: {diagnostics.get('numeric_valid_count', 0)}")
        print(f"    - Text normalizations: {diagnostics.get('text_cleanups_count', 0)}")
        rel = diagnostics.get("relevance_breakdown", {})
        if rel:
            print(f"    - Discussion relevance flags: {rel}")

    print("\n  Sample Standardized Atomic Records:")
    for rec in evidence[:6]:
        eid = rec.get("evidence_id", "")
        src = rec.get("source", "")
        src = getattr(src, "value", str(src))
        etype = rec.get("evidence_type", "")
        etype = getattr(etype, "value", str(etype))
        title = rec.get("title", "")
        val = rec.get("value")
        unit = rec.get("unit") or ""
        val_str = f" [Value: {val} {unit}]" if val is not None else ""
        rel = rec.get("relevance")
        rel_str = f" [Relevance: {rel}]" if rel else ""
        print(f"    [{src} | {etype}] {title}{val_str}{rel_str}")
        print(f"      ID: {eid} | Time: {rec.get('time_period') or 'N/A'}")


def _print_retrieval_documents(documents: list, diagnostics: dict):
    if not documents and not diagnostics:
        return
    _sep("RETRIEVAL-READY DOCUMENTS (STEP 4)")
    print(f"\n  Total Retrieval Documents Ready: {len(documents)}")
    if diagnostics:
        print("  Diagnostics:")
        print(f"    - Input cleaned records: {diagnostics.get('input_records_count', 0)}")
        print(f"    - Retrieval-ready documents: {diagnostics.get('retrieval_ready_count', 0)}")
        print(f"    - Excluded off-topic/irrelevant records: {diagnostics.get('excluded_irrelevant_count', 0)}")
        by_src = diagnostics.get("by_source", {})
        if by_src:
            print(f"    - By source: {by_src}")
        excl = diagnostics.get("excluded_irrelevant_documents", [])
        if excl:
            print("    - Excluded records audit:")
            for e in excl[:3]:
                print(f"      * [{e.get('document_id')}] {e.get('title')}: {e.get('relevance_reason')}")

    print("\n  Sample Retrieval-Ready Documents:")
    for doc in documents[:5]:
        doc_id = doc.get("document_id", "")
        meta = doc.get("metadata", {})
        src = meta.get("source", "unknown")
        geo = meta.get("formatted_geography") or "N/A"
        text = doc.get("text", "")
        preview = text[:140] + ("..." if len(text) > 140 else "")
        print(f"    [{doc_id}] ({src} | {geo})")
        print(f"      Text: {preview}")
        print()


def _print_document_chunks(chunks: list, diagnostics: dict):
    if not chunks and not diagnostics:
        return
    _sep("SOURCE-AWARE DOCUMENT CHUNKS (STEP 5)")
    print(f"\n  Total Chunks Generated: {len(chunks)}")
    if diagnostics:
        cfg = diagnostics.get("config", {})
        print(f"  Configuration:")
        print(f"    - Max chunk characters: {cfg.get('max_chunk_chars', 'N/A')}")
        print(f"    - Narrative overlap characters: {cfg.get('chunk_overlap_chars', 'N/A')}")
        print(f"    - Minimum useful characters: {cfg.get('min_chunk_chars', 'N/A')}")

        print("  Diagnostics:")
        print(f"    - Input documents: {diagnostics.get('input_documents_count', 0)}")
        print(f"    - Eligible documents: {diagnostics.get('eligible_documents_count', 0)}")
        print(f"    - Skipped ineligible/empty documents: {diagnostics.get('skipped_ineligible_count', 0)}")
        by_src = diagnostics.get("by_source", {})
        if by_src:
            print(f"    - Chunks per source: {by_src}")
        by_strat = diagnostics.get("by_strategy", {})
        if by_strat:
            print(f"    - Chunks per strategy: {by_strat}")

        skipped = diagnostics.get("skipped_documents", [])
        if skipped:
            print("    - Skipped documents audit:")
            for s in skipped[:3]:
                print(f"      * [{s.get('document_id')}] Reason: {s.get('reason')}")

    print("\n  Sample Document Chunks:")
    for chunk in chunks[:5]:
        cid = chunk.get("chunk_id", "")
        strat = chunk.get("chunking_strategy", "unknown")
        meta = chunk.get("metadata", {})
        src = meta.get("source", "unknown")
        char_cnt = chunk.get("char_count", 0)
        text = chunk.get("text", "")
        preview = text[:130] + ("..." if len(text) > 130 else "")
        print(f"    [{cid}] ({src} | strategy: {strat} | {char_cnt} chars)")
        print(f"      Content: {preview}")
        print()


def _print_chunk_embeddings(embeddings: list, diagnostics: dict):
    if not embeddings and not diagnostics:
        return
    _sep("VALIDATED CHUNK EMBEDDINGS (STEP 6)")
    print(f"\n  Total Embeddings Generated: {len(embeddings)}")
    if diagnostics:
        model = diagnostics.get("embedding_model", "N/A")
        dims = diagnostics.get("embedding_dimensions", "N/A")
        print(f"  Model Architecture:")
        print(f"    - Embedding model: {model}")
        print(f"    - Vector dimensions: {dims}")
        print(f"  Diagnostics:")
        print(f"    - Eligible chunks: {diagnostics.get('eligible_chunks_count', 0)}")
        print(f"    - Batches processed: {diagnostics.get('batches_processed', 0)}")
        print(f"    - Failed chunks: {diagnostics.get('failed_chunks_count', 0)}")
        issues = diagnostics.get("issues", [])
        if issues:
            print(f"    - Issues reported:")
            for iss in issues[:3]:
                print(f"      * {iss}")

    print("\n  Sample Embedding Records:")
    for emb in embeddings[:3]:
        cid = emb.get("chunk_id", "")
        vec = emb.get("embedding", [])
        dims = len(vec)
        preview_vec = [round(x, 4) for x in vec[:4]]
        meta = emb.get("metadata", {})
        src = meta.get("source", "unknown")
        print(f"    [{cid}] ({src} | {dims} dims)")
        print(f"      Vector sample: [{', '.join(str(x) for x in preview_vec)}, ...]")
        print()


def _print_vector_store_results(diagnostics: dict, count: int):
    if not diagnostics:
        return
    stored = diagnostics.get("successfully_stored_count", count)
    total_col = diagnostics.get("total_collection_count", stored)
    col_name = diagnostics.get("collection_name", "market_evidence_chunks")
    p_dir = diagnostics.get("persistence_directory", "data/chroma")
    model = diagnostics.get("embedding_model")
    dims = diagnostics.get("embedding_dimensions")
    dims_str = f" ({dims} dims)" if dims else ""

    print(f"\n  ChromaDB Vector Store (Step 7):")
    print(f"    Collection:  '{col_name}' in {p_dir}")
    print(f"    Indexed:     {stored} chunks stored in this run (Total in collection: {total_col})")
    if model:
        print(f"    Model:       {model}{dims_str}")
    if diagnostics.get("issues"):
        print(f"    Store issues: {len(diagnostics['issues'])}")
        for iss in diagnostics["issues"]:
            print(f"      - {iss}")


def parse_cli_args(argv=None):
    """
    Parse command-line arguments for IndiValidate Market Analyzer using argparse.
    Handles --help cleanly, displays available options, and exits without launching research.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="main.py",
        description="IndiValidate - Multi-Persona Synthetic Simulation & Empirical Evidence Market Analyzer.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--idea",
        type=str,
        default=None,
        help="Business idea to analyze. If omitted, prompts interactively.",
    )
    parser.add_argument(
        "--intake",
        action="store_true",
        default=False,
        help="Launch the interactive 5-question founder intake questionnaire before research.",
    )
    parser.add_argument(
        "--intake-file",
        type=str,
        default=None,
        help="Path to JSON file containing founder context (non-interactive alternative to --intake).",
    )
    parser.add_argument(
        "--personas",
        type=int,
        default=10,
        help="Number of synthetic customer personas to generate and evaluate (1-25).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Bounded worker concurrency for persona evaluation (1-10).",
    )
    parser.add_argument(
        "--export-json",
        nargs="?",
        const="market_validation_report.json",
        default=None,
        help="Export structured report to JSON file (default: market_validation_report.json).",
    )
    parser.add_argument(
        "--export-md",
        nargs="?",
        const="market_validation_report.md",
        default=None,
        help="Export report to Markdown file (default: market_validation_report.md).",
    )
    parser.add_argument(
        "--query",
        nargs="?",
        const="labour workforce employment in Gujarat",
        default=None,
        help="Demonstrate semantic evidence retrieval over indexed ChromaDB chunks without running full pipeline.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    import json
    import sys

    args = parse_cli_args(argv)

    if args.query:
        run_retrieval_demo(args.query)
        return

    idea = args.idea
    if not idea:
        try:
            idea = input("\nEnter your business idea:\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  [Aborted] No business idea provided.")
            return

    if not idea:
        print("\n  [Error] Business idea cannot be empty.")
        return

    founder_context = None
    if args.intake:
        print("\n  [Founder Intake: ENABLED] Starting 5-question intake questionnaire...")
        try:
            from app.intake.questionnaire import run_founder_intake_questionnaire
            founder_context = run_founder_intake_questionnaire()
        except (EOFError, KeyboardInterrupt) as err:
            print(f"\n  [Founder Intake Error] Interactive input unavailable or interrupted ({err}).")
            print("  To supply founder context non-interactively, use --intake-file <path_to_json>.")
            founder_context = None
    elif args.intake_file:
        try:
            with open(args.intake_file, "r", encoding="utf-8") as f:
                founder_context = json.load(f)
            print(f"\n  [Founder Intake: FILE LOADED] Loaded founder context from '{args.intake_file}'.")
        except Exception as e:
            print(f"\n  [Founder Intake Error] Failed to read intake file '{args.intake_file}': {e}")
            founder_context = None
    else:
        print("\n  [Founder Intake: SKIPPED] (Use --intake to supply founder context)")

    persona_count = max(1, min(25, args.personas if args.personas is not None else 10))
    eval_concurrency = max(1, min(10, args.concurrency if args.concurrency is not None else 3))

    initial_state = {
        "idea": idea,
        "persona_count": persona_count,
        "evaluation_concurrency": eval_concurrency,
    }
    if founder_context is not None:
        initial_state["founder_context"] = founder_context

    graph = build_graph()
    result = graph.invoke(initial_state)

    # ================================================================
    # PREPROCESSING RESULTS
    # ================================================================
    _sep("INDIVALIDATE — MARKET ANALYSIS")

    print(f"\nIdea:     {result.get('idea', '')}")
    print(f"Category: {result.get('category', '')}")

    print("\nKeywords:")
    for kw in result.get("keywords", []):
        print(f"  - {kw}")

    print(f"\nTarget:   {result.get('target_segment', '')}")
    print(f"Location: {result.get('location', '')}")
    print(f"Research context: {result.get('research_type', '')}")

    fc = result.get("founder_context")
    if fc:
        print("\nFounder Context [SELF-REPORTED CLAIMS — NOT EXTERNAL EVIDENCE]:")
        print(f"  Target customer:   {fc.get('customer_category', '')}")
        if fc.get("customer_description"):
            print(f"  Description:       {fc.get('customer_description')}")
        if fc.get("launch_geography"):
            print(f"  Launch geography:  {fc.get('launch_geography')} (Scope: {fc.get('geographic_scope', 'not_decided')})")
        print(f"  Problem stated:    {fc.get('problem_description', '')}")
        if fc.get("known_alternatives"):
            print(f"  Alternatives:      {', '.join(fc.get('known_alternatives'))}")
        if fc.get("pricing_model") and fc.get("pricing_model") != "not_decided":
            p_str = fc.get("pricing_model")
            if fc.get("expected_price"):
                p_str += f" ({fc.get('expected_price')})"
            print(f"  Pricing model:     {p_str}")
        if fc.get("validation_stage"):
            print(f"  Validation stage:  {fc.get('validation_stage')}")

    # ================================================================
    # RESEARCH RESULTS
    # ================================================================
    _sep("PHASE 1 RESEARCH RESULTS")

    _print_reddit_evidence(result.get("reddit_evidence", []))
    _print_trends_evidence(result.get("trends_evidence", []))
    _print_census_evidence(result.get("census_evidence", []))
    _print_plfs_evidence(result.get("plfs_evidence", []))

    # ================================================================
    # COMMON NORMALIZED EVIDENCE
    # ================================================================
    _print_normalized_evidence(result.get("normalized_evidence", []))

    # ================================================================
    # STANDARDIZED & CLEANED EVIDENCE (STEP 3)
    # ================================================================
    _print_cleaned_evidence(result.get("cleaned_evidence", []), result.get("cleaning_diagnostics", {}))

    # ================================================================
    # RETRIEVAL-READY DOCUMENTS (STEP 4)
    # ================================================================
    _print_retrieval_documents(result.get("retrieval_documents", []), result.get("document_diagnostics", {}))

    # ================================================================
    # SOURCE-AWARE DOCUMENT CHUNKS (STEP 5)
    # ================================================================
    _print_document_chunks(result.get("document_chunks", []), result.get("chunking_diagnostics", {}))

    # ================================================================
    # VALIDATED CHUNK EMBEDDINGS (STEP 6)
    # ================================================================
    _print_chunk_embeddings(result.get("chunk_embeddings", []), result.get("embedding_diagnostics", {}))

    # ================================================================
    # CHROMADB VECTOR STORE (STEP 7)
    # ================================================================
    _print_vector_store_results(result.get("vector_store_diagnostics", {}), result.get("vector_store_count", 0))

    # ================================================================
    # SYNTHETIC PERSONAS (STEP 9)
    # ================================================================
    _print_personas_section(result.get("personas", []), result.get("persona_generation_diagnostics", {}))

    # ================================================================
    # MULTI-PERSONA EVALUATIONS & INTENT SIMULATION (STEP 10)
    # ================================================================
    _print_persona_evaluations(result.get("persona_evaluations", []), result.get("persona_evaluation_diagnostics", {}))

    # ================================================================
    # MARKET ANALYSIS & EVIDENCE CROSS-VALIDATION (STEP 11)
    # ================================================================
    _print_market_analysis_section(result.get("market_analysis", {}), result.get("market_analysis_diagnostics", {}))

    # ================================================================
    # FINAL STRUCTURED MARKET-VALIDATION REPORT (STEP 12)
    # ================================================================
    _print_market_validation_report(result.get("market_report", {}), result.get("market_report_diagnostics", {}))

    # ================================================================
    # EXPORT OPTIONS
    # ================================================================
    export_json_path = args.export_json
    export_md_path = args.export_md

    if export_json_path and result.get("market_report"):
        with open(export_json_path, "w", encoding="utf-8") as f:
            json.dump(result["market_report"], f, indent=2)
        print(f"\n  [Export] Report JSON saved to: {export_json_path}")

    if export_md_path and result.get("market_report"):
        try:
            from app.schemas.market_report import MarketValidationReport
            report_obj = MarketValidationReport.model_validate(result["market_report"])
            md_content = report_obj.to_markdown()
        except Exception:
            md_content = f"# Market Validation Report\n\n```json\n{json.dumps(result['market_report'], indent=2)}\n```"
        with open(export_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"  [Export] Report Markdown saved to: {export_md_path}")

    # ================================================================
    # ERRORS SECTION
    # ================================================================
    _print_research_errors_section(result.get("research_errors", []))

    print(f"\nResearch complete: {result.get('research_complete', False)}")
    _sep()


def _print_personas_section(personas: list, diagnostics: dict):
    if not personas:
        if diagnostics and diagnostics.get("issues"):
            print(f"\n  Synthetic Personas: 0 generated (Issues: {', '.join(diagnostics['issues'])})")
        return

    c_type = diagnostics.get("customer_type", "consumer")
    req = diagnostics.get("requested_count", len(personas))
    print(f"\n  Evidence-Grounded Synthetic Customer Personas (Step 9):")
    print(f"    Generated: {len(personas)} / {req} requested (Type: {c_type.upper()})\n")

    for idx, p in enumerate(personas, 1):
        pid = p.get("persona_id", f"p_{idx}")
        name = p.get("name", "Unnamed")
        seg = p.get("segment", "Target")
        age = p.get("age_band", "N/A")
        occ = p.get("occupation", "N/A")
        inc = p.get("income_band", "N/A")
        geo = p.get("geography", {})
        loc_str = f"{geo.get('district', '')}, {geo.get('state', '')}".strip(", ") if geo else "N/A"

        print(f"    [{pid}] {name}")
        print(f"      Segment:        {seg} | Location: {loc_str}")
        print(f"      Demographics:   Age: {age} | Occupation: {occ} | Income: {inc}")

        # Behavioral hypotheses
        bh = p.get("behavioral_hypotheses", {})
        if bh:
            scales = [
                f"PriceSens={bh.get('price_sensitivity', '-')}/10",
                f"Convenience={bh.get('convenience_preference', '-')}/10",
                f"BrandTrust={bh.get('brand_trust_importance', '-')}/10",
                f"RiskTol={bh.get('risk_tolerance', '-')}/10",
                f"Digital={bh.get('digital_adoption', '-')}/10",
            ]
            print(f"      Behavioral:     {' | '.join(scales)}")

        # Goals and constraints
        needs = p.get("goals_and_needs", [])
        pains = p.get("pain_points", [])
        constraints = p.get("purchasing_constraints", [])
        if needs:
            print(f"      Core Needs:     {'; '.join(needs[:2])}")
        if pains:
            print(f"      Pain Points:    {'; '.join(pains[:2])}")
        if constraints:
            print(f"      Constraints:    {'; '.join(constraints[:2])}")

        # Provenance
        prov = p.get("provenance", {})
        assumptions = prov.get("explicit_assumptions", [])
        if assumptions:
            print(f"      Assumptions:    {'; '.join(assumptions[:2])}")
        print()


def _print_persona_evaluations(evaluations: list, diagnostics: dict):
    if not evaluations:
        if diagnostics and diagnostics.get("issues"):
            print(f"\n  Persona Evaluations (Step 10): 0 completed (Issues: {', '.join(diagnostics['issues'])})")
        return

    _sep("SIMULATED MULTI-PERSONA EVALUATION & INTENT (STEP 10)")
    total = diagnostics.get("total_personas", len(evaluations))
    eval_count = len(evaluations)
    print(f"\n  Simulated Customer Feedback & Adoption Hypotheses:")
    print(f"    Completed: {eval_count} / {total} personas evaluated")
    if diagnostics.get("evaluation_time_seconds"):
        workers_info = f" (Concurrency: {diagnostics.get('concurrency', 1)} workers)" if diagnostics.get("concurrency") else ""
        print(f"    Evaluation Elapsed Time: {diagnostics['evaluation_time_seconds']:.1f}s{workers_info}")
    print(f"    NOTE: Evaluations are synthetic simulations, NOT real customer survey results or conversion probabilities.")

    avgs = diagnostics.get("score_averages", {})
    if avgs:
        print(f"\n    [Aggregate Score Averages Across Personas (1-10 Scale)]")
        print(f"      Interest Score:           {avgs.get('avg_interest_score', '-')}/10 (1=Uninterested, 10=High interest)")
        print(f"      Simulated Purchase Intent:{avgs.get('avg_simulated_purchase_intent', '-')}/10 (1=Definitely not, 10=Inclined)")
        print(f"      Perceived Value:          {avgs.get('avg_perceived_value_score', '-')}/10 (1=Negligible, 10=Transformative)")
        print(f"      Affordability:            {avgs.get('avg_affordability_score', '-')}/10 (1=Unaffordable, 10=Easily affordable)")
        print(f"      Adoption Barrier:         {avgs.get('avg_adoption_barrier_score', '-')}/10 (1=Frictionless, 10=High inertia)")

    print(f"\n    [Individual Persona Evaluations]")
    for idx, e in enumerate(evaluations, 1):
        pid = e.get("persona_id", f"persona_{idx}")
        inte = e.get("interest_score", "-")
        intent = e.get("simulated_purchase_intent", "-")
        val = e.get("perceived_value_score", "-")
        aff = e.get("affordability_score", "-")
        barr = e.get("adoption_barrier_score", "-")

        print(f"    [{pid}]")
        print(f"      Scores (1-10):  Interest={inte}/10 | Intent={intent}/10 | Value={val}/10 | Affordability={aff}/10 | Barrier={barr}/10")

        # Qualitative reactions
        pos = e.get("positive_aspects", [])
        neg = e.get("negative_aspects", [])
        if pos:
            print(f"      Positive:       {'; '.join(pos[:2])}")
        if neg:
            print(f"      Negative/Risks: {'; '.join(neg[:2])}")

        # Needs and pricing
        addressed = e.get("needs_addressed", [])
        unmet = e.get("needs_unmet", [])
        if addressed:
            print(f"      Needs Met:      {'; '.join(addressed[:2])}")
        if unmet:
            print(f"      Needs Unmet:    {'; '.join(unmet[:2])}")

        price_cond = e.get("price_is_conditional", False)
        pricing_str = e.get("pricing_considerations") or "N/A"
        cond_label = " [UNSPECIFIED IN PROPOSAL - CONDITIONAL]" if price_cond else ""
        print(f"      Pricing:        {pricing_str[:120]}{cond_label}")

        # Evidence and uncertainty
        ev_ids = e.get("supporting_evidence_ids", [])
        gaps = e.get("evidence_gaps", [])
        assumptions = e.get("unsupported_assumptions", [])
        if ev_ids:
            print(f"      Evidence Cited: {', '.join(ev_ids)}")
        if gaps:
            print(f"      Evidence Gaps:  {'; '.join(gaps[:2])}")
        if assumptions:
            print(f"      Assumptions:    {'; '.join(assumptions[:2])}")

        reasons = e.get("reasons_for_assessment", "")
        if reasons:
            print(f"      Reasoning:      {reasons[:140]}...")
        print()


def _print_market_analysis_section(analysis: dict, diagnostics: dict):
    if not analysis:
        if diagnostics and diagnostics.get("issues"):
            print(f"\n  Market Analysis (Step 11): Not available (Issues: {', '.join(diagnostics['issues'])})")
        return

    _sep("AGGREGATED MARKET ANALYSIS & EVIDENCE CROSS-VALIDATION (STEP 11)")
    stats = analysis.get("overall_statistics", {})
    total_p = stats.get("total_personas_generated", 0)
    success_p = stats.get("successful_evaluations_count", 0)
    failed_p = stats.get("failed_evaluations_count", 0)

    print(f"\n  Overall Evaluation Synthesis:")
    print(f"    Evaluations Evaluated: {success_p} / {total_p} personas (Failed/Excluded: {failed_p})")
    print(f"    NOTE: Synthesized findings reflect synthetic persona simulations, NOT population survey statistics.")

    # 1. Descriptive statistics
    print(f"\n  [Numerical Metric Distributions (1-10 Scale)]")
    metric_map = [
        ("Interest Score", stats.get("interest_stats", {})),
        ("Simulated Purchase Intent", stats.get("purchase_intent_stats", {})),
        ("Perceived Value", stats.get("perceived_value_stats", {})),
        ("Affordability", stats.get("affordability_stats", {})),
        ("Adoption Barrier (Higher=Harder)", stats.get("adoption_barrier_stats", {})),
    ]
    for label, m in metric_map:
        if not m:
            continue
        cnt = m.get("count", 0)
        mean_v = m.get("mean", "-")
        med_v = m.get("median", "-")
        std_v = m.get("std_dev", "-")
        min_v = m.get("min_val", "-")
        max_v = m.get("max_val", "-")
        dist = m.get("distribution", {})
        # compact histogram
        dist_str = " ".join(f"{k}:{v}" for k, v in dist.items() if v > 0) or "None"
        print(f"    - {label:<34}: Mean={mean_v:<4} | Med={med_v:<4} | StdDev={std_v:<4} | Range=[{min_v}, {max_v}] (N={cnt})")
        print(f"      Distribution (Score:Count): {dist_str}")

    # 2. Segment Analysis
    segs = analysis.get("segment_analyses", [])
    if segs:
        print(f"\n  [Segment Comparative Receptivity & Barriers]")
        for s in segs:
            s_name = s.get("segment_name", "Unknown")
            p_cnt = s.get("persona_count", 0)
            e_cnt = s.get("evaluated_count", 0)
            m_int = s.get("median_interest", "-")
            m_pi = s.get("median_purchase_intent", "-")
            m_aff = s.get("median_affordability", "-")
            m_bar = s.get("median_adoption_barrier", "-")
            top_f = s.get("top_valued_features", [])
            top_c = s.get("major_concerns", [])
            print(f"    * Segment: '{s_name}' (Evaluated: {e_cnt}/{p_cnt})")
            print(f"      Medians: Interest={m_int}/10 | Purchase Intent={m_pi}/10 | Affordability={m_aff}/10 | Adoption Barrier={m_bar}/10")
            if top_f:
                print(f"      Valued:  {'; '.join(top_f[:2])}")
            if top_c:
                print(f"      Barriers:{'; '.join(top_c[:2])}")
            print(f"      Summary: {s.get('affordability_and_adoption_summary', '')}")
            print()

    # 3. Top Features
    feats = analysis.get("features_analysis", [])
    if feats:
        print(f"  [Key Features & Proposed Capabilities]")
        for f in feats[:5]:
            fname = f.get("feature_name", "Feature")
            pos_c = f.get("positive_mentions_count", 0)
            neg_c = f.get("negative_mentions_count", 0)
            val = f.get("validation", {})
            st = val.get("evidence_status", "unknown").upper()
            expl = val.get("explanation", "")
            print(f"    - '{fname}' (Pos: {pos_c} personas | Neg: {neg_c} personas)")
            print(f"      Evidence Status: [{st}] {expl[:120]}")
            if val.get("caveats"):
                print(f"      Caveats:         {'; '.join(val['caveats'][:2])}")
        print()

    # 4. Recurring Concerns
    concs = analysis.get("concerns_analysis", [])
    if concs:
        print(f"  [Recurring Customer Concerns & Objections]")
        for c in concs[:5]:
            cname = c.get("concern_name", "Concern")
            cat = c.get("category", "general")
            m_cnt = c.get("persona_mentions_count", 0)
            val = c.get("validation", {})
            st = val.get("evidence_status", "unknown").upper()
            expl = val.get("explanation", "")
            print(f"    - '{cname}' [{cat.replace('_', ' ').title()}] (Raised by {m_cnt} personas)")
            print(f"      Evidence Status: [{st}] {expl[:120]}")
        print()

    # 5. Disagreement Areas
    dis = analysis.get("disagreement_areas", [])
    if dis:
        print(f"  [Areas of Divergence & Persona Disagreement]")
        for d in dis:
            topic = d.get("topic", "Divergence")
            spread = d.get("divergence_spread", "-")
            expl = d.get("explanation", "")
            print(f"    ! {topic} (Spread/StdDev: {spread})")
            print(f"      Explanation: {expl}")
        print()

    # 6. Evidence Coverage & Uncertainty Audit
    cov = analysis.get("evidence_coverage", {})
    if cov:
        ratio = cov.get("evidence_coverage_ratio", 0.0)
        tot_find = cov.get("total_findings_evaluated", 0)
        sup = cov.get("supported_count", 0)
        contra = cov.get("contradicted_count", 0)
        mix = cov.get("mixed_count", 0)
        insuf = cov.get("insufficient_evidence_count", 0)
        na = cov.get("not_applicable_count", 0)
        srcs = cov.get("sources_represented", [])

        print(f"  [Evidence Cross-Validation Audit]")
        print(f"    Total Findings Evaluated: {tot_find}")
        print(f"    Validation Breakdown:     Supported={sup} | Contradicted={contra} | Mixed={mix} | Insufficient={insuf} | Subjective/NA={na}")
        print(f"    Evidence Coverage Ratio:  {ratio:.2f} ({ratio*100:.0f}% of findings backed by external empirical sources)")
        print(f"    NOTE: Coverage ratio is an empirical data audit measure, NOT a probability of startup success.")
        if srcs:
            print(f"    Sources Corroborating:    {', '.join(srcs)}")

        pricing_notes = cov.get("unresolved_pricing_assumptions", [])
        if pricing_notes:
            print(f"    Pricing Assumptions:      {'; '.join(pricing_notes)}")

        gaps = cov.get("important_evidence_gaps", [])
        if gaps:
            print(f"    Key Empirical Gaps:       {'; '.join(gaps[:3])}")
        print()


def _print_market_validation_report(report: dict, diagnostics: dict):
    if not report:
        if diagnostics and diagnostics.get("issues"):
            print(f"\n  Market Validation Report (Step 12): Not available (Issues: {', '.join(diagnostics['issues'])})")
        return

    _sep("FINAL STRUCTURED MARKET-VALIDATION REPORT (STEP 12)")
    rep_id = report.get("report_id", "REPORT")
    gen_at = report.get("generated_at", "")
    print(f"\n  Report Identifier: {rep_id} (Generated: {gen_at})")
    print("  STATUS: Empirical Evidence Cross-Validation & Synthetic Simulation Synthesis")
    print("  BOUNDARY: No startup success probabilities, market size estimations, or go/no-go verdicts.")

    # 1. Executive Summary
    es = report.get("executive_summary", {})
    if es:
        print(f"\n  [Executive Summary]")
        print(f"    Concept:        {es.get('idea_description', '')}")
        segs = es.get("target_customer_segments", [])
        print(f"    Target Segments:{', '.join(segs) if segs else 'General Market'}")

        prom = es.get("strongest_promising_signals", [])
        if prom:
            print(f"    Promising Signals:")
            for p in prom[:3]:
                print(f"      + {p}")

        risks = es.get("key_risks_and_barriers", [])
        if risks:
            print(f"    Risks & Barriers:")
            for r in risks[:3]:
                print(f"      - {r}")

        unresolved = es.get("critical_unresolved_questions", [])
        if unresolved:
            print(f"    Unresolved Questions:")
            for u in unresolved[:2]:
                print(f"      ? {u}")

        nxt = es.get("next_validation_priority", "")
        if nxt:
            print(f"    Next Validation Priority:")
            print(f"      > {nxt}")

    # 2. What Appears Promising
    promising = report.get("what_appears_promising", [])
    if promising:
        print(f"\n  [What Appears Promising ({len(promising)} hypotheses)]")
        for p in promising[:4]:
            fid = p.get("finding_id", "P")
            claim = p.get("claim_or_hypothesis", "")
            cat = p.get("category", "")
            st = p.get("evidence_validation_status", "unknown").upper()
            segs = p.get("relevant_segments", [])
            rat = p.get("rationale", "")
            test = p.get("suggested_real_world_validation", "")
            print(f"    * [{fid}] {claim}")
            print(f"      Category: {cat} | Status: [{st}] | Segments: {', '.join(segs)}")
            if rat:
                print(f"      Rationale: {rat[:130]}...")
            if test:
                print(f"      Next Test: {test}")
            print()

    # 3. What May Not Work
    barriers = report.get("what_may_not_work", [])
    if barriers:
        print(f"  [What May Not Work ({len(barriers)} risks/barriers)]")
        for b in barriers[:4]:
            fid = b.get("finding_id", "R")
            concern = b.get("concern_or_barrier", "")
            cat = b.get("barrier_category", "")
            st = b.get("evidence_validation_status", "unknown").upper()
            segs = b.get("relevant_segments", [])
            mit = b.get("suggested_mitigation_or_test", "")
            print(f"    * [{fid}] {concern} [{cat}]")
            print(f"      Status: [{st}] | Segments: {', '.join(segs)}")
            if mit:
                print(f"      Mitigation / Test: {mit}")
            print()

    # 4. Segment Comparison
    seg_comps = report.get("segment_comparison", [])
    if seg_comps:
        print(f"  [Segment Comparison ({len(seg_comps)} segments)]")
        print("  NOTE: Persona counts represent synthetic personas generated, NOT population share or market size.")
        for sc in seg_comps:
            sname = sc.get("segment_name", "")
            pcnt = sc.get("persona_count", 0)
            ecnt = sc.get("evaluated_personas_count", 0)
            scores = sc.get("median_scores", {})
            # Prefer canonical short keys; fall back to prefixed keys for backward compatibility
            m_int = scores.get("interest") if scores.get("interest") is not None else scores.get("median_interest", "-")
            m_pi = scores.get("purchase_intent") if scores.get("purchase_intent") is not None else scores.get("median_purchase_intent", "-")
            m_aff = scores.get("affordability") if scores.get("affordability") is not None else scores.get("median_affordability", "-")
            m_bar = scores.get("adoption_barrier") if scores.get("adoption_barrier") is not None else scores.get("median_adoption_barrier", "-")
            vf = sc.get("valued_features", [])
            mc = sc.get("main_concerns", [])
            test = sc.get("suggested_validation_experiment", "")
            print(f"    * Segment: '{sname}' (Synthetic Personas: {ecnt}/{pcnt})")
            print(f"      Median Scores: Interest={m_int}/10 | Intent={m_pi}/10 | Affordability={m_aff}/10 | Barrier={m_bar}/10")
            if vf:
                print(f"      Valued Features: {'; '.join(vf[:2])}")
            if mc:
                print(f"      Main Concerns:   {'; '.join(mc[:2])}")
            if test:
                print(f"      Validation Test: {test}")
            print()

    # 5. Prioritized Feature Hypotheses
    feats = report.get("feature_prioritization", [])
    if feats:
        print(f"  [Feature Prioritization Hypotheses ({len(feats)} features)]")
        for f in feats[:5]:
            fname = f.get("feature_name", "")
            pos = f.get("positive_mentions_count", 0)
            neg = f.get("negative_mentions_count", 0)
            tier = f.get("priority_tier", "")
            st = f.get("evidence_validation_status", "unknown").upper()
            unc = f.get("main_uncertainty", "")
            step = f.get("suggested_next_validation_step", "")
            print(f"    - '{fname}' [{tier}] (Pos: {pos} | Neg: {neg} | Status: [{st}])")
            if unc:
                print(f"      Uncertainty: {unc[:120]}")
            if step:
                print(f"      Next Step:   {step}")
        print()

    # 6. Pricing and Affordability
    pa = report.get("pricing_and_affordability", {})
    if pa:
        print(f"  [Pricing and Affordability]")
        pstat = pa.get("pricing_status", "")
        cond = pa.get("price_is_conditional", True)
        print(f"    Pricing Status: {pstat}")
        if cond:
            print("    NOTE: Price is conditional/unspecified. Simulated scores reflect hypothetical affordability.")
        print(f"    Affordability Summary: {pa.get('simulated_affordability_summary', '')}")
        plfs_bench = pa.get("contextual_earnings_evidence")
        if plfs_bench:
            loc = plfs_bench.get("location", "National")
            # Support both key names: regular_salaried_avg_inr (canonical) and regular_wage_mean (legacy)
            avg_w_raw = plfs_bench.get("regular_salaried_avg_inr") or plfs_bench.get("regular_wage_mean")
            if avg_w_raw is None:
                avg_w_str = "Unavailable"
            elif isinstance(avg_w_raw, (int, float)):
                avg_w_str = f"{avg_w_raw:,.2f}"
            else:
                avg_w_str = str(avg_w_raw)
            print(f"    Contextual Labour Benchmark ({loc}): Regular Wage Mean ~ Rs. {avg_w_str}/mo (Source: PLFS 2025)")
            print("    CAVEAT: Income context does NOT establish customer willingness to pay.")
        wtp_test = pa.get("recommended_wtp_experiment", "")
        if wtp_test:
            print(f"    Recommended WTP Test: {wtp_test}")
        print()

    # 7. Disagreement and Uncertainty
    disagreements = report.get("disagreement_and_uncertainty", [])
    if disagreements:
        print(f"  [Disagreements and Divergence]")
        for d in disagreements[:4]:
            top = d.get("topic", "")
            spr = d.get("observed_spread_or_difference", "")
            cls = d.get("is_observed_or_hypothesized", "")
            exp = d.get("plausible_explanation", "")
            res = d.get("evidence_needed_to_resolve", "")
            print(f"    ! {top} (Spread: {spr}) [{cls}]")
            print(f"      Explanation: {exp}")
            if res:
                print(f"      Resolving Evidence Needed: {res}")
        print()

    # 8. Evidence Coverage Audit
    cov = report.get("evidence_coverage_audit", {})
    if cov:
        ratio = cov.get("evidence_coverage_ratio", 0.0)
        tot = cov.get("total_findings_evaluated", 0)
        sup = cov.get("supported_count", 0)
        contra = cov.get("contradicted_count", 0)
        mix = cov.get("mixed_count", 0)
        insuf = cov.get("insufficient_evidence_count", 0)
        na = cov.get("not_applicable_count", 0)
        print(f"  [Evidence Coverage Audit]")
        print(f"    Coverage Ratio: {ratio:.2f} ({ratio*100:.0f}% of findings evaluated against external empirical evidence)")
        print(f"    Audit Breakdown: Total={tot} | Supported={sup} | Contradicted={contra} | Mixed={mix} | Insufficient={insuf} | Subjective/NA={na}")
        print(f"    Formula Explanation: {cov.get('coverage_formula_explanation', '')}")
        srcs = cov.get("sources_represented", [])
        if srcs:
            print(f"    Represented Sources: {', '.join(srcs)}")
        gaps = cov.get("important_evidence_gaps", [])
        if gaps:
            print(f"    Key Empirical Gaps: {'; '.join(gaps[:2])}")
        print()

    # 9. Recommended Next Experiments
    recs = report.get("recommended_experiments", [])
    if recs:
        print(f"  [Recommended Next Validation Experiments ({len(recs)} experiments)]")
        for r in recs[:4]:
            rid = r.get("recommendation_id", "EXP")
            q = r.get("question_to_validate", "")
            t_seg = r.get("target_segment", "")
            etype = r.get("suggested_experiment_type", "")
            metric = r.get("measurement_metric", "")
            rule = r.get("decision_rule_hypothesis", "")
            print(f"    > [{rid}] {q}")
            print(f"      Segment: {t_seg} | Test: {etype}")
            print(f"      Measurement Metric: {metric}")
            print(f"      Decision Rule Hypothesis: {rule}")
            print()

    # 10. Core Research Questions Analysis (Evidence-grounded or LLM Fallback)
    rqas = report.get("research_questions_analysis", [])
    if rqas:
        print(f"  [Core Research Questions Analysis ({len(rqas)} questions evaluated)]")
        for idx, rqa in enumerate(rqas, 1):
            q = rqa.get("question", "")
            basis = rqa.get("basis", "model_knowledge").upper()
            ans = rqa.get("answer", "")
            srcs = rqa.get("supporting_sources", [])
            conf = rqa.get("confidence", "")
            req_ext = rqa.get("requires_external_validation", True)
            src_str = ", ".join(srcs) if srcs else "None (Model Knowledge Fallback)"
            ext_str = "YES (Requires Field Validation)" if req_ext else "NO (Empirically Corroborated)"

            print(f"    Q{idx}: {q}")
            print(f"      Basis: [{basis}] | External Validation Required: {ext_str}")
            print(f"      Answer: {ans}")
            print(f"      Confidence: {conf}")
            print(f"      Sources: {src_str}")
            assumptions = rqa.get("assumptions", [])
            if assumptions:
                print(f"      Assumptions: {'; '.join(assumptions[:2])}")
            limits = rqa.get("limitations", [])
            if limits:
                print(f"      Limitations: {'; '.join(limits[:2])}")
            print()


def run_retrieval_demo(query: str, top_k: int = 3, persist_dir: str = "data/chroma", collection_name: str = "market_evidence_chunks"):
    """Demonstrate semantic evidence retrieval over the persisted ChromaDB collection (Step 8)."""
    import sys
    from app.rag.retriever import EvidenceRetriever
    from app.rag.vector_store import ChromaVectorStore

    store = ChromaVectorStore(persist_directory=persist_dir, collection_name=collection_name)
    if store.count() == 0:
        print(f"\n  [Retriever Demo] Collection '{collection_name}' in '{persist_dir}' is empty.")
        print("  Run research first to index evidence.")
        return

    retriever = EvidenceRetriever(vector_store=store)
    try:
        res = retriever.retrieve(query=query, top_k=top_k)
        print(f"\n  [Semantic Evidence Retrieval Demo]")
        print(f"    Query:      '{query}'")
        print(f"    Collection: '{collection_name}' (Total in DB: {store.count()})")
        print(f"    Retrieved:  {res.total_retrieved} chunk(s)\n")

        if not res.chunks:
            print("    No relevant evidence found for this query.")
            return

        for idx, chunk in enumerate(res.chunks, 1):
            geo = f"{chunk.geography.get('district', '')}, {chunk.geography.get('state', '')}" if chunk.geography else "N/A"
            time_p = chunk.time_period or "N/A"
            print(f"    {idx}. [{chunk.chunk_id}]")
            print(f"       Source:      {chunk.source.upper()} | Evidence Type: {chunk.evidence_type or 'N/A'}")
            print(f"       Geography:   {geo} | Period: {time_p}")
            print(f"       Distance:    {chunk.distance:.4f} (ChromaDB vector distance)")
            print(f"       Observation: {chunk.text}")
            if chunk.limitations:
                print(f"       Caveats:     {'; '.join(chunk.limitations)}")
            print()
    except Exception as e:
        print(f"\n  [Retriever Demo Error]: {e}")


if __name__ == "__main__":
    main()