from langgraph.graph import StateGraph, START, END

from app.state import MarketState

from app.nodes.idea_analysis import analyze_idea
from app.nodes.keywords import extract_keywords
from app.nodes.target import identify_target
from app.nodes.location import identify_location
from app.nodes.research_decision import research_decision
from app.nodes.research import run_research
from app.nodes.persona_generation import generate_personas_node
from app.nodes.persona_evaluation import evaluate_personas_node
from app.nodes.market_analysis import analyze_market_node
from app.nodes.market_report import build_market_report_node
from app.nodes.gemini_context import gemini_context_node, is_evidence_sufficient


# =========================================================
# RESEARCH CONTEXT NODES
# These three nodes represent the research CONTEXT decision.
# They set the research_type (already done by research_decision),
# then all three converge into run_research which collects
# real evidence from all four sources.
# =========================================================

def location_research(state: MarketState):
    """
    Research context: location-based.
    This node is reached when a specific location was identified.
    It simply passes through to run_research.
    """
    print(">>> RESEARCH CONTEXT: Location-based")
    return {}


def consumer_research(state: MarketState):
    """
    Research context: consumer-focused.
    This node is reached when a target customer was identified.
    It simply passes through to run_research.
    """
    print(">>> RESEARCH CONTEXT: Consumer")
    return {}


def general_research(state: MarketState):
    """
    Research context: general market.
    This node is reached as the default fallback.
    It simply passes through to run_research.
    """
    print(">>> RESEARCH CONTEXT: General")
    return {}


# =========================================================
# SYNCHRONIZATION NODE
# =========================================================

def preprocessing_complete(state: MarketState):
    print(">>> PREPROCESSING COMPLETE")
    return {}


# =========================================================
# CONDITIONAL ROUTER
# routes to location_research, consumer_research, or general_research
# based on what the research_decision node set in research_type
# =========================================================

def route_research(state: MarketState):
    return state["research_type"]


def route_evidence_sufficiency(state: MarketState) -> str:
    """
    Evaluate empirical evidence sufficiency after run_research.
    If sufficient, proceed directly to Mistral persona generation.
    If absent or insufficient, route to Gemini to generate domain context & hypotheses.
    """
    if is_evidence_sufficient(state):
        return "sufficient"
    return "insufficient"


# =========================================================
# BUILD GRAPH
# =========================================================

def build_graph():

    graph = StateGraph(MarketState)

    # -----------------------------------------------------
    # Add preprocessing nodes
    # -----------------------------------------------------

    graph.add_node("analyze_idea", analyze_idea)
    graph.add_node("extract_keywords", extract_keywords)
    graph.add_node("identify_target", identify_target)
    graph.add_node("identify_location", identify_location)

    # -----------------------------------------------------
    # Add synchronization node
    # -----------------------------------------------------

    graph.add_node(
        "preprocessing_complete",
        preprocessing_complete
    )

    # -----------------------------------------------------
    # Add conditional decision node
    # -----------------------------------------------------

    graph.add_node(
        "research_decision",
        research_decision
    )

    # -----------------------------------------------------
    # Add research context nodes
    # (these represent the conditional routing decision)
    # -----------------------------------------------------

    graph.add_node(
        "location_research",
        location_research
    )

    graph.add_node(
        "consumer_research",
        consumer_research
    )

    graph.add_node(
        "general_research",
        general_research
    )

    # -----------------------------------------------------
    # Add Phase 1 real research node
    # (called after the context decision, collects all evidence)
    # -----------------------------------------------------

    graph.add_node(
        "run_research",
        run_research
    )

    graph.add_node(
        "gemini_context_fallback",
        gemini_context_node
    )

    graph.add_node(
        "generate_personas",
        generate_personas_node
    )

    graph.add_node(
        "evaluate_personas",
        evaluate_personas_node
    )

    graph.add_node(
        "analyze_market",
        analyze_market_node
    )

    graph.add_node(
        "build_market_report",
        build_market_report_node
    )

    # =====================================================
    # START
    # =====================================================

    graph.add_edge(
        START,
        "analyze_idea"
    )

    # =====================================================
    # PARALLEL BRANCHES
    # (all three run in parallel after analyze_idea)
    # =====================================================

    graph.add_edge(
        "analyze_idea",
        "extract_keywords"
    )

    graph.add_edge(
        "analyze_idea",
        "identify_target"
    )

    graph.add_edge(
        "analyze_idea",
        "identify_location"
    )

    # =====================================================
    # WAIT FOR ALL THREE BRANCHES
    # (LangGraph waits for all three before proceeding)
    # =====================================================

    graph.add_edge(
        "extract_keywords",
        "preprocessing_complete"
    )

    graph.add_edge(
        "identify_target",
        "preprocessing_complete"
    )

    graph.add_edge(
        "identify_location",
        "preprocessing_complete"
    )

    # =====================================================
    # DECISION
    # =====================================================

    graph.add_edge(
        "preprocessing_complete",
        "research_decision"
    )

    # =====================================================
    # CONDITIONAL EDGES
    # Routes to the appropriate research context node
    # =====================================================

    graph.add_conditional_edges(
        "research_decision",
        route_research,
        {
            "location_based": "location_research",
            "consumer": "consumer_research",
            "general": "general_research"
        }
    )

    # =====================================================
    # ALL CONTEXT NODES LEAD TO run_research
    # (regardless of which context was selected,
    # Phase 1 collects all four evidence sources)
    # =====================================================

    graph.add_edge(
        "location_research",
        "run_research"
    )

    graph.add_edge(
        "consumer_research",
        "run_research"
    )

    graph.add_edge(
        "general_research",
        "run_research"
    )

    # =====================================================
    # END
    # =====================================================

    # If empirical evidence is sufficient, proceed directly to Mistral persona generation.
    # If absent or insufficient, route to Gemini for domain context & hypotheses first.
    graph.add_conditional_edges(
        "run_research",
        route_evidence_sufficiency,
        {
            "sufficient": "generate_personas",
            "insufficient": "gemini_context_fallback",
        }
    )

    graph.add_edge(
        "gemini_context_fallback",
        "generate_personas"
    )

    graph.add_edge(
        "generate_personas",
        "evaluate_personas"
    )

    graph.add_edge(
        "evaluate_personas",
        "analyze_market"
    )

    graph.add_edge(
        "analyze_market",
        "build_market_report"
    )

    graph.add_edge(
        "build_market_report",
        END
    )

    # =====================================================
    # COMPILE
    # =====================================================

    return graph.compile()