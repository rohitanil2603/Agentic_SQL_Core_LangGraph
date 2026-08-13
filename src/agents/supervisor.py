"""
Supervisor Agent (A0): Routes queries as Simple or Complex.
"""
import logging
from langchain_core.messages import HumanMessage

from agents.state import GraphState
from agents.llm_utils import get_llm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def agent_a0_supervisor(state: GraphState) -> GraphState:
    """
    Agent A0: Supervisor
    Analyzes user input and decides if query is "Simple" or "Complex".
    Routes required analytical queries through the full pipeline.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with plan field populated
    """
    logger.info("Agent A0 (Supervisor): Analyzing query complexity...")
    
    query = state["query"]
    
    # Early detection of overly vague/ambiguous queries (before routing)
    query_lower = query.lower().strip()
    vague_patterns = [
        "analysis of",
        "analyze",
        "overview",
        "summary",
        "tell me about",
        "what can you tell me",
        "information about"
    ]
    
    # Check if query is too vague (only if it's very short or matches vague patterns)
    is_vague = any(pattern in query_lower for pattern in vague_patterns) and len(query.split()) <= 5
    
    if is_vague:
        logger.warning(f"Detected vague query in supervisor: '{query}' - Providing helpful guidance")
        state["intent"] = "GENERAL_QUERY"
        state["result"] = f"I'd be happy to help! Your query '{query}' is a bit general. Could you be more specific? For example:\n\n" \
                         f"- 'List the top 10 products by sales'\n" \
                         f"- 'Show me product categories'\n" \
                         f"- 'What are the best-selling products?'\n" \
                         f"- 'Show me products with low stock levels'\n\n" \
                         f"Or ask about orders, deliveries, warehouses, customers, or reviews!"
        state["plan"] = "Vague query - providing guidance"
        return state
    
    # Check for explicit chart/visualization requests BEFORE routing
    # These MUST go through Complex path to generate Python code for charts
    chart_keywords = [
        "chart", "graph", "plot", "visualization", "visualize",
        "as a line", "as a bar", "as a pie", "line chart", "bar chart", "pie chart",
        "plot", "plotting", "graphical", "visual"
    ]
    has_chart_request = any(keyword in query_lower for keyword in chart_keywords)
    
    # CRITICAL: If chart request detected, skip LLM and force Complex routing immediately
    if has_chart_request:
        plan = "Complex query - routing through full pipeline (explicit chart request detected)"
        logger.info(f"Query classified as Complex - explicit chart request detected: '{query}'")
        state["plan"] = plan
        return state
    
    # Determine if query is simple (direct SQL) or complex (needs full pipeline)
    prompt = f"""You are a query routing supervisor for a database system.

Analyze the following user query and determine if it is:
- "Simple": Can be answered with a direct SQL query (e.g., "How many orders are there?", "List all manufacturers")
- "Complex": Requires analysis, aggregation, or visualization (e.g., "Show me revenue trends", "What's the distribution of delivery statuses?", "Plot average ratings as a line chart")

CRITICAL: If the user explicitly requests a chart, graph, plot, or visualization (e.g., "as a line chart", "plot", "bar chart"), it MUST be "Complex" to generate Python code for charting.

User Query: "{query}"

Respond with ONLY "Simple" or "Complex"."""

    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        complexity = response.content.strip().lower()
        
        if "complex" in complexity:
            plan = "Complex query - routing through full pipeline (Router -> Code Generator -> Reviewer -> Executor -> Presenter)"
            logger.info("Query classified as Complex - full pipeline")
        else:
            plan = "Simple query - direct SQL execution"
            logger.info("Query classified as Simple - direct execution")
        
        state["plan"] = plan
        return state
        
    except Exception as e:
        logger.error(f"Error in Agent A0: {str(e)}")
        state["plan"] = "Complex query - routing through full pipeline"
        return state

