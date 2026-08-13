"""
LangGraph compilation: Defines the agent graph structure and routing.
"""
import logging
from typing import Literal
from langgraph.graph import StateGraph, END

from agents.state import GraphState
from agents.supervisor import agent_a0_supervisor
from agents.specialized import (
    agent_a1_router,
    agent_a2_code_generator,
    agent_a4_executor
)
from agents.post_processor import agent_a3_post_processor

# AST post-processor is always enabled (old reviewer removed for code clarity)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def should_continue(state: GraphState) -> Literal["simple", "complex", "__end__"]:
    """
    Routing function: Determines if query should go through simple or complex path.
    
    Args:
        state: Current graph state
        
    Returns:
        "simple", "complex", or "__end__" based on plan
    """
    # If result is already set (e.g., vague query guidance), end immediately
    current_result = state.get("result")
    if current_result and isinstance(current_result, str) and ("Could you be more specific" in current_result or "I'd be happy to help" in current_result):
        return "__end__"
    
    plan = state.get("plan", "")
    if "Simple" in plan:
        return "simple"
    else:
        return "complex"


def simple_query_node(state: GraphState) -> GraphState:
    """
    Simple query path: Direct SQL execution without full pipeline.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with results
    """
    logger.info("Simple query path: Direct SQL execution")
    
    query = state["query"]
    
    # For simple queries, generate SQL directly and execute
    from agents.tools import get_sql_db, get_db_schema
    from agents.llm_utils import get_llm
    from agents.security import validate_sql_security
    from langchain_core.messages import HumanMessage
    
    llm = get_llm()
    schema = get_db_schema()
    
    prompt = f"""You are a SQL query generator for a robot vacuum depot database.

Database Schema:
{schema}

User Query: "{query}"

Generate a SQL query that answers the user's question.

SECURITY RULES (CRITICAL):
- You MUST ONLY generate SELECT queries
- FORBIDDEN: DROP, DELETE, TRUNCATE, ALTER, CREATE, INSERT, UPDATE, or any DDL/DML commands
- If the user asks for destructive operations, return an error message instead

IMPORTANT:
- If a table name is shown in quotes (e.g., "order"), you MUST use quotes in your SQL query
- For SQLite, use double quotes for table/column names that are reserved keywords

CRITICAL RULE FOR DERIVED FIELDS:
- The "order" table contains a derived field called "delivery_status" that contains pre-computed delivery status values
- When queries relate to delivery status (delayed, delivered, canceled, etc.), ALWAYS use the delivery_status column
- DO NOT recalculate delivery status by comparing actual_delivery_date and expected_delivery_date directly
- The delivery_status field values include: 'Delivered', 'Delayed', 'Canceled', 'Canceled - Fraud', 'On Time', 'Pending'
- Always prefer using derived/computed fields from the schema rather than recalculating them in queries

CRITICAL RULE FOR LOCATION-BASED QUERIES:
- When filtering by location (e.g., "California warehouses", "warehouses in California"):
  - Check the warehouse table's warehouse_street_address or warehouse_zip_code directly
  - California zip codes typically range from 90000 to 96162
  - DO NOT use distribution_center addresses to identify warehouse locations
  - If you need to join with distribution_center, use the warehouse_distribution_center relationship table, not address matching

- Return ONLY the SQL query, no explanations or markdown."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        sql_code = response.content.strip()
        
        # Clean up SQL
        if sql_code.startswith("```"):
            lines = sql_code.split("\n")
            sql_code = "\n".join(lines[1:-1]) if len(lines) > 2 else sql_code
        
        # Check for dangerous patterns before execution
        is_safe, error_message = validate_sql_security(sql_code)
        if not is_safe:
            logger.error(f"Dangerous SQL pattern detected - Rejecting for safety")
            state["result"] = error_message
            state["code"] = None
            state["code_type"] = "sql"
            state["sql_query"] = None
            return state
        
        # Execute SQL
        sql_db = get_sql_db()
        result = sql_db.run(sql_code)
        
        # Extract column names from SQL query
        from agents.specialized import extract_column_names_from_sql
        column_names = extract_column_names_from_sql(sql_code)
        
        state["code"] = sql_code
        state["result"] = result
        state["column_names"] = column_names if column_names else None
        state["code_type"] = "sql"
        state["sql_query"] = sql_code
        state["python_code"] = None
        state["chart_type"] = None
        state["plan"] = "Simple query executed"
        
        logger.info(f"Simple query executed: {result[:100] if result else 'No result'}...")
        return state
        
    except Exception as e:
        logger.error(f"Error in simple query execution: {str(e)}")
        state["result"] = f"Error: {str(e)}"
        return state


def compile_graph() -> StateGraph:
    """
    Compile the LangGraph with all agents and routing logic.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Compiling LangGraph...")
    
    # Create the graph
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("supervisor", agent_a0_supervisor)
    workflow.add_node("simple_query", simple_query_node)
    workflow.add_node("router", agent_a1_router)
    workflow.add_node("code_generator", agent_a2_code_generator)
    
    # Add post-processor node (AST-based)
    workflow.add_node("post_processor", agent_a3_post_processor)
    workflow.add_node("executor", agent_a4_executor)
    # Note: Presenter logic merged into executor, reviewer replaced by post_processor
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add conditional edges from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        should_continue,
        {
            "simple": "simple_query",
            "complex": "router",
            "__end__": END
        }
    )
    
    # Simple path: simple_query -> END
    workflow.add_edge("simple_query", END)
    
    # Complex path: router -> code_generator -> post_processor -> executor -> END
    workflow.add_edge("router", "code_generator")
    workflow.add_edge("code_generator", "post_processor")
    workflow.add_edge("post_processor", "executor")
    # Executor includes presenter logic, so go directly to END
    workflow.add_edge("executor", END)
    
    # Compile the graph
    app = workflow.compile()
    
    logger.info("LangGraph compiled successfully")
    return app


# Export compiled graph
graph = compile_graph()

