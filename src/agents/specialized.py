"""
Specialized Agents: A1 (Router), A2 (Code Generator), A4 (Executor)
Note: A3 (Reviewer) placed in post_processor, (Presenter) logic in A4 
"""
import logging
import re
from enum import Enum
from typing import Dict, Any, Optional, List
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from langchain_core.messages import HumanMessage

from agents.tools import get_sql_db, get_python_repl, get_db_schema
from agents.state import GraphState
from agents.llm_utils import get_llm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_column_names_from_sql(sql_query: str) -> List[str]:
    """
    Extract column names from SQL SELECT statement.
    Handles AS aliases and basic column references.
    
    Args:
        sql_query: SQL query string
        
    Returns:
        List of column names (with aliases if present)
    """
    try:
        # Remove comments and normalize whitespace
        sql = re.sub(r'--.*?$', '', sql_query, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        sql = ' '.join(sql.split())
        
        # Extract SELECT clause (up to FROM)
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return []
        
        select_clause = select_match.group(1).strip()
        
        # Split by comma, handling nested parentheses
        columns = []
        current_col = ""
        paren_depth = 0
        
        for char in select_clause:
            if char == '(':
                paren_depth += 1
                current_col += char
            elif char == ')':
                paren_depth -= 1
                current_col += char
            elif char == ',' and paren_depth == 0:
                if current_col.strip():
                    columns.append(current_col.strip())
                current_col = ""
            else:
                current_col += char
        
        if current_col.strip():
            columns.append(current_col.strip())
        
        # Extract column names and aliases
        column_names = []
        for col in columns:
            col = col.strip()
            # Check for AS alias
            as_match = re.search(r'\s+AS\s+["\']?(\w+)["\']?$', col, re.IGNORECASE)
            if as_match:
                column_names.append(as_match.group(1))
            else:
                # Check for space-separated alias (SQLite allows this)
                parts = col.split()
                if len(parts) >= 2 and not parts[-1].upper() in ['ASC', 'DESC']:
                    # Might be an alias
                    alias = parts[-1].strip('"\'')
                    if alias and not alias.upper() in ['ASC', 'DESC', 'NULL', 'NOT']:
                        column_names.append(alias)
                    else:
                        # Use the last part of the column expression
                        last_part = parts[-1].strip('"\'')
                        column_names.append(last_part if last_part else f"Column_{len(column_names)}")
                else:
                    # Use the column expression itself, cleaned up
                    clean_col = re.sub(r'^.*\.', '', col).strip('"\'')
                    column_names.append(clean_col if clean_col else f"Column_{len(column_names)}")
        
        return column_names if column_names else []
    
    except Exception as e:
        logger.warning(f"Error extracting column names from SQL: {str(e)}")
        return []


class Intent(Enum):
    """Intent enumeration for semantic routing."""
    DELAYED_DELIVERIES_BY_MODEL = "DELAYED_DELIVERIES_BY_MODEL"
    WAREHOUSE_BELOW_RESTOCK = "WAREHOUSE_BELOW_RESTOCK"
    DELAYED_DELIVERIES_BY_ZIP = "DELAYED_DELIVERIES_BY_ZIP"
    BEST_MANUFACTURER_BY_REVIEW = "BEST_MANUFACTURER_BY_REVIEW"
    REVENUE_TRENDS = "REVENUE_TRENDS"
    DELIVERY_STATUS_DISTRIBUTION = "DELIVERY_STATUS_DISTRIBUTION"
    REVIEW_RATINGS_BY_BRAND = "REVIEW_RATINGS_BY_BRAND"
    SHIPPING_COST_COMPARISON = "SHIPPING_COST_COMPARISON"
    GENERAL_QUERY = "GENERAL_QUERY"


# Visualization configuration mapping Intents to output formats
# NOTE: This config controls PRESENTATION ONLY. It does NOT contain SQL.
# These are DEFAULT preferences that can be overridden by explicit user requests.
VIZ_CONFIG: Dict[Intent, Dict[str, str]] = {
    Intent.DELAYED_DELIVERIES_BY_MODEL: {"mode": "table"},
    Intent.WAREHOUSE_BELOW_RESTOCK: {"mode": "table"},
    Intent.DELAYED_DELIVERIES_BY_ZIP: {"mode": "table"},
    Intent.BEST_MANUFACTURER_BY_REVIEW: {"mode": "table"},
    Intent.REVENUE_TRENDS: {"mode": "chart", "type": "line"},
    Intent.DELIVERY_STATUS_DISTRIBUTION: {"mode": "chart", "type": "pie"},
    Intent.REVIEW_RATINGS_BY_BRAND: {"mode": "chart", "type": "bar"},
    Intent.SHIPPING_COST_COMPARISON: {"mode": "chart", "type": "bar"},
    Intent.GENERAL_QUERY: {"mode": "table"},  # Default to table
}


def parse_user_visualization_preference(query: str) -> Optional[Dict[str, str]]:
    """
    Parse user's explicit visualization preference from query.
    Handles positive requests, negative constraints, and various phrasings.
    Implements "Defaults with User Overrides" logic.
    
    Args:
        query: User's query string
        
    Returns:
        Dict with 'mode' and optionally 'type' if preference found, None otherwise
    """
    query_lower = query.lower()
    
    # Check for negative constraints first (e.g., "not in pie chart", "do not use bar chart")
    if "not" in query_lower:
        # Check for "do not use" / "don't use" / "avoid" / "exclude" patterns
        if any(phrase in query_lower for phrase in [
            "not in pie", "not a pie", "not pie chart", "not pie graph",
            "do not use pie", "don't use pie", "avoid pie", "exclude pie",
            "do not use a pie", "don't use a pie"
        ]):
            # User doesn't want pie chart - prefer bar or table
            if "bar" in query_lower:
                return {"mode": "chart", "type": "bar"}
            elif "line" in query_lower:
                return {"mode": "chart", "type": "line"}
            elif "table" in query_lower or "text" in query_lower:
                return {"mode": "table"}
            else:
                return {"mode": "chart", "type": "bar"}  # Default alternative to pie
        elif any(phrase in query_lower for phrase in [
            "not in bar", "not a bar", "not bar chart", "not bar graph",
            "do not use bar", "don't use bar", "avoid bar", "exclude bar",
            "do not use a bar", "don't use a bar", "do not use bar chart", "don't use bar chart"
        ]):
            if "pie" in query_lower:
                return {"mode": "chart", "type": "pie"}
            elif "line" in query_lower:
                return {"mode": "chart", "type": "line"}
            elif "table" in query_lower or "text" in query_lower:
                return {"mode": "table"}
            else:
                # Default alternative to bar - prefer pie for distribution/comparison, table for lists
                if "distribution" in query_lower or "percentage" in query_lower or "compare" in query_lower:
                    return {"mode": "chart", "type": "pie"}
                else:
                    return {"mode": "table"}
        elif any(phrase in query_lower for phrase in [
            "not in line", "not a line", "not line chart",
            "do not use line", "don't use line", "avoid line", "exclude line"
        ]):
            if "bar" in query_lower:
                return {"mode": "chart", "type": "bar"}
            elif "pie" in query_lower:
                return {"mode": "chart", "type": "pie"}
            elif "table" in query_lower:
                return {"mode": "table"}
            else:
                return {"mode": "chart", "type": "bar"}
    
    # Check for explicit table/text requests (more patterns)
    # Also check for "list", "show", "display" with numbers (e.g., "list 5", "show 3")
    if any(phrase in query_lower for phrase in [
        "in table", "as a table", "as table", "show table", "give table", "display table",
        "in text", "as text", "text format", "textual format", "as text format"
    ]):
        return {"mode": "table"}
    
    # Check for "list X" or "show X" patterns (typically table requests)
    import re
    if re.search(r'\blist\s+\d+', query_lower) or re.search(r'\bshow\s+\d+', query_lower):
        return {"mode": "table"}
    
    # Check for "show me all", "list all", "ranked by" patterns (table requests)
    if any(phrase in query_lower for phrase in [
        "show me all", "list all", "show all", "all manufacturers", "all products",
        "ranked by", "ranked", "top", "bottom"
    ]):
        return {"mode": "table"}
    
    # Check for chart type requests (expanded patterns)
    if any(phrase in query_lower for phrase in [
        "bar chart", "bar graph", "as a bar", "vertical bar", "horizontal bar", "vertical bar chart", "horizontal bar chart"
    ]):
        return {"mode": "chart", "type": "bar"}
    elif any(phrase in query_lower for phrase in [
        "pie chart", "pie graph", "as a pie"
    ]):
        return {"mode": "chart", "type": "pie"}
    elif any(phrase in query_lower for phrase in [
        "line chart", "line graph", "as a line"
    ]):
        return {"mode": "chart", "type": "line"}
    elif any(phrase in query_lower for phrase in [
        "scatter plot", "scatter chart", "scatter graph"
    ]):
        return {"mode": "chart", "type": "scatter"}
    
    # Check for output preference context from UI (if still used)
    if "prefers table" in query_lower or "prefer table" in query_lower:
        return {"mode": "table"}
    elif "prefers chart" in query_lower or "prefer chart" in query_lower:
        # Try to infer chart type from context
        if "bar" in query_lower:
            return {"mode": "chart", "type": "bar"}
        elif "pie" in query_lower:
            return {"mode": "chart", "type": "pie"}
        elif "line" in query_lower:
            return {"mode": "chart", "type": "line"}
        elif "scatter" in query_lower:
            return {"mode": "chart", "type": "scatter"}
        else:
            return {"mode": "chart", "type": "bar"}  # Default chart type
    
    return None


def agent_a1_router(state: GraphState) -> GraphState:
    """
    Agent A1: Intent Router
    Maps natural language query to Intent enum using LLM.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with intent field populated
    """
    logger.info("Agent A1 (Router): Classifying intent...")
    
    query = state["query"]
    
    # Early detection of overly vague/ambiguous queries
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
        logger.warning(f"Detected vague query: '{query}' - Providing helpful guidance")
        state["intent"] = Intent.GENERAL_QUERY.value
        state["result"] = f"I'd be happy to help! Your query '{query}' is a bit general. Could you be more specific? For example:\n\n" \
                         f"- 'List the top 10 products by sales'\n" \
                         f"- 'Show me product categories'\n" \
                         f"- 'What are the best-selling products?'\n" \
                         f"- 'Show me products with low stock levels'\n\n" \
                         f"Or ask about orders, deliveries, warehouses, customers, or reviews!"
        return state
    
    # Create prompt for intent classification
    intent_list = "\n".join([f"- {intent.value}" for intent in Intent])
    
    prompt = f"""You are an intent classifier for a robot vacuum depot database system.

Your task is to classify the user's query into one of these intents:

{intent_list}

IMPORTANT GUIDELINES:
- If the query asks for trends over time (daily, weekly, monthly, quarterly, yearly), classify as REVENUE_TRENDS or create a chart
- If the query asks to "list", "show", or "display" specific items/rows, it's likely a table request (GENERAL_QUERY)
- If the query asks for distribution or breakdown, consider DELIVERY_STATUS_DISTRIBUTION
- If the query asks to "compare" values (especially shipping costs, ratings, costs), consider SHIPPING_COST_COMPARISON or REVIEW_RATINGS_BY_BRAND
- If the query mentions "shipping cost" and "carrier", classify as SHIPPING_COST_COMPARISON

User Query: "{query}"

Respond with ONLY the intent name (e.g., "REVENUE_TRENDS" or "GENERAL_QUERY").
Do not include any explanation or additional text."""

    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        intent_str = response.content.strip()
        
        # Map string to Intent enum
        intent = None
        for intent_enum in Intent:
            if intent_enum.value == intent_str:
                intent = intent_enum
                break
        
        if intent is None:
            logger.warning(f"Could not map '{intent_str}' to Intent enum, defaulting to GENERAL_QUERY")
            intent = Intent.GENERAL_QUERY
        
        logger.info(f"Intent detected: {intent.value}")
        state["intent"] = intent.value
        return state
        
    except Exception as e:
        logger.error(f"Error in Agent A1: {str(e)}")
        state["intent"] = Intent.GENERAL_QUERY.value
        return state


def agent_a2_code_generator(state: GraphState) -> GraphState:
    """
    Agent A2: Code Generator
    Generates SQL or Python code dynamically based on Schema + Intent + User Query.
    
    CRITICAL: Schema is injected into the system prompt.
    Implements "Defaults with User Overrides" logic for visualization preferences.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with code field populated
    """
    logger.info("Agent A2 (Code Generator): Generating code...")
    
    # Early return if result is already set (e.g., from A1 for vague queries)
    if state.get("result") and not state.get("code"):
        logger.info("Result already set, skipping code generation")
        return state
    
    query = state["query"]
    intent_str = state.get("intent", "GENERAL_QUERY")
    intent = Intent(intent_str)
    
    # CRITICAL: Get schema for injection
    schema_description = get_db_schema()
    
    # Priority 1: Check for explicit user preference
    user_pref = parse_user_visualization_preference(query)
    
    if user_pref:
        # User explicitly requested a format -> Override VIZ_CONFIG
        logger.info(f"User preference detected: {user_pref}, overriding VIZ_CONFIG")
        viz_config = user_pref
    else:
        # Priority 2: Check for implicit chart requests (time series, trends, counts over time)
        # BUT: Respect VIZ_CONFIG for specific intents (e.g., DELIVERY_STATUS_DISTRIBUTION should be pie)
        query_lower = query.lower()
        
        # Only override VIZ_CONFIG for time-series queries if intent doesn't have a specific chart type
        # This ensures DELIVERY_STATUS_DISTRIBUTION (pie) and other specific intents are respected
        is_time_series = any(phrase in query_lower for phrase in [
            "daily", "weekly", "monthly", "quarterly", "yearly", "trend", "over time",
            "count of", "number of"
        ]) and any(phrase in query_lower for phrase in ["order", "revenue", "sales"])
        
        # Check if intent has a specific chart type in VIZ_CONFIG
        intent_viz_config = VIZ_CONFIG.get(intent, {"mode": "table"})
        has_specific_chart_type = (intent_viz_config.get("mode") == "chart" and 
                                  intent_viz_config.get("type") is not None)
        
        if is_time_series and not has_specific_chart_type:
            # Only override if it's a time-series AND intent doesn't have a specific chart type
            logger.info(f"Detected time-series query, defaulting to line chart")
            viz_config = {"mode": "chart", "type": "line"}
        else:
            # Priority 3: Fall back to VIZ_CONFIG defaults (respects pie chart for DELIVERY_STATUS_DISTRIBUTION)
            viz_config = intent_viz_config
            logger.info(f"Using VIZ_CONFIG default for {intent.value}: {viz_config}")
    
    # Determine if we need SQL or Python (for charting)
    needs_chart = viz_config.get("mode") == "chart"
    
    if needs_chart:
        # Generate Python code for charting
        chart_type = viz_config.get("type", "bar")
        
        prompt = f"""You are a Python code generator for data visualization.

Database Schema:
{schema_description}

User Query: "{query}"
Intent: {intent.value}
Chart Type: {chart_type}

Generate Python code that:
1. Connects to the SQLite database at 'robot_vacuum.db' using sqlite3
2. Executes a SQL query to fetch the required data based on the user query
3. Creates a {chart_type} chart using plotly (use plotly.graph_objects or plotly.express)
4. Stores the figure in a variable named 'figure' (for retrieval)

SECURITY RULES (CRITICAL):
- You MUST ONLY use SELECT queries in your SQL code
- FORBIDDEN: DROP, DELETE, TRUNCATE, ALTER, CREATE, INSERT, UPDATE, or any DDL/DML commands
- This is a read-only database interface

CRITICAL RULES:
- Use the exact table and column names from the schema above
- If a table name is shown in quotes (e.g., "order"), you MUST use quotes in your SQL query
- For SQLite, use double quotes for table/column names that are reserved keywords (e.g., FROM "order" not FROM order)

CRITICAL RULE FOR TIME SERIES (Monthly Revenue):
- When asked for 'Monthly' trends or 'monthly revenue':
  1. In SQL: Use strftime('%Y-%m', OrderDate) AS 'Month' to create YYYY-MM format strings (e.g., "2025-10")
  2. In Python: AFTER reading from SQL with pd.read_sql_query(), you MUST convert the Month column to string:
     df['Month'] = df['Month'].astype(str)
  3. DO NOT use pd.to_datetime() on the Month column - it must remain as string
  4. In Plotly: 
     - Use x='Month' (the string column) for the X-axis
     - For plotly.express: After creating the figure, call figure.update_layout(xaxis_type='category') to ensure categorical display
     - For plotly.graph_objects: Set xaxis_type='category' in layout to prevent datetime conversion
     - Example: figure = px.line(df, x='Month', y='Value'); figure.update_layout(xaxis_type='category')
- Group by the Month string, not raw timestamps
- After reading data from SQL, convert the Month column to string: df['Month'] = df['Month'].astype(str)
- When creating the plotly figure, use x='Month' and call figure.update_layout(xaxis_type='category')

AGGREGATION RULES:
- When calculating aggregations (AVG, SUM, COUNT, etc.) with GROUP BY, ensure you group by the appropriate non-aggregated columns
- Use proper JOINs when accessing related tables through foreign keys

- The SQL query must be dynamically generated based on the user query
- Use AS aliases in SQL to create readable column names for the DataFrame
- Return ONLY the Python code, no explanations, no markdown code blocks, no backticks
- The code should be executable as-is
- Use plotly.graph_objects.Figure or plotly.express for charts
- IMPORTANT: Do not include ```python or ``` at the start/end of your response

Example structure:
```python
import sqlite3
import pandas as pd
import plotly.express as px
# ... your code ...
figure = px.bar(...)  # or go.Figure(...)
```

Generate the code:"""
        
    else:
        # Generate SQL query
        prompt = f"""You are a SQL query generator for a robot vacuum depot database.

Database Schema:
{schema_description}

User Query: "{query}"
Intent: {intent.value}

Generate a SQL query that answers the user's question.

SECURITY RULES (CRITICAL):
- You MUST ONLY generate SELECT queries
- FORBIDDEN: DROP, DELETE, TRUNCATE, ALTER, CREATE, INSERT, UPDATE, or any DDL/DML commands
- If the user asks for destructive operations, return an error message instead
- This is a read-only database interface

CRITICAL RULES:
- Use the exact table and column names from the schema above
- If a table name is shown in quotes (e.g., "order"), you MUST use quotes in your SQL query
- For SQLite, use double quotes for table/column names that are reserved keywords
- ALWAYS use AS aliases to create readable, human-friendly column names
- Column names should match the context of the user's question (use descriptive aliases instead of raw column names)

CRITICAL RULE FOR LOCATION-BASED QUERIES:
- When filtering by location (e.g., "California warehouses", "warehouses in California"):
  - Check the warehouse table's warehouse_street_address or warehouse_zip_code directly
  - California zip codes typically range from 90000 to 96162
  - DO NOT use distribution_center addresses to identify warehouse locations
  - If you need to join with distribution_center, use the warehouse_distribution_center relationship table, not address matching

CRITICAL RULE FOR TIME SERIES (Monthly Revenue):
- When asked for 'Monthly' trends or 'monthly revenue':
  1. In SQL: Use strftime('%Y-%m', OrderDate) AS 'Month' to create YYYY-MM format strings
  2. Group by the Month string, not raw timestamps
  3. The Month column will be a string (e.g., "2025-10"), NOT a datetime

CRITICAL RULE FOR DERIVED FIELDS:
- The "order" table contains a derived field called "delivery_status" that contains pre-computed delivery status values
- When queries relate to delivery status (delayed, delivered, canceled, etc.), ALWAYS use the delivery_status column
- DO NOT recalculate delivery status by comparing actual_delivery_date and expected_delivery_date directly
- The delivery_status field values include: 'Delivered', 'Delayed', 'Canceled', 'Canceled - Fraud', 'On Time', 'Pending'
- Always prefer using derived/computed fields from the schema rather than recalculating them in queries

AGGREGATION RULES:
- When calculating aggregations (AVG, SUM, COUNT, etc.) with GROUP BY, ensure you group by the appropriate non-aggregated columns
- Use proper JOINs when accessing related tables through foreign keys

- The query must be dynamically generated based on the user query
- Return ONLY the SQL query, no explanations
- Do not include markdown code blocks or backticks
- Use proper SQL syntax compatible with SQLite

Generate the SQL query:"""
    
    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        code = response.content.strip()
        
        # Aggressive code cleaning - remove markdown code blocks more robustly
        # Remove markdown code blocks more aggressively
        if code.startswith("```python"):
            code = code[9:]  # Remove ```python
        elif code.startswith("```"):
            code = code[3:]  # Remove ```
        
        if code.endswith("```"):
            code = code[:-3]  # Remove trailing ```
        
        # Remove any leading/trailing whitespace and newlines
        code = code.strip()
        
        # Store code type in state (CRITICAL: prevents A4 from recalculating)
        state["code_type"] = "python" if needs_chart else "sql"
        
        # Populate code metadata for explainability
        if needs_chart:
            # For Python code, extract SQL query and store metadata
            state["python_code"] = code
            state["chart_type"] = chart_type
            
            # Try to extract SQL query from Python code (look for pd.read_sql_query or conn.execute)
            import re
            # Pattern 1: pd.read_sql_query("SELECT ...", conn)
            sql_match = re.search(r"pd\.read_sql_query\(['\"](.*?)['\"]", code, re.DOTALL)
            if not sql_match:
                # Pattern 2: conn.execute("SELECT ...")
                sql_match = re.search(r"conn\.execute\(['\"](.*?)['\"]", code, re.DOTALL)
            if not sql_match:
                # Pattern 3: cursor.execute("SELECT ...")
                sql_match = re.search(r"cursor\.execute\(['\"](.*?)['\"]", code, re.DOTALL)
            if not sql_match:
                # Pattern 4: query = "SELECT ..." (multi-line string)
                sql_var_match = re.search(r"query\s*=\s*['\"](.*?)['\"]", code, re.DOTALL | re.MULTILINE)
                if sql_var_match:
                    state["sql_query"] = sql_var_match.group(1).strip()
                else:
                    # Pattern 5: query = """SELECT ...""" (triple quotes)
                    sql_triple_match = re.search(r"query\s*=\s*['\"]{3}(.*?)['\"]{3}", code, re.DOTALL)
                    if sql_triple_match:
                        state["sql_query"] = sql_triple_match.group(1).strip()
                    else:
                        state["sql_query"] = None
            else:
                state["sql_query"] = sql_match.group(1).strip()
        else:
            # For SQL code, store it directly
            state["sql_query"] = code
            state["python_code"] = None
            state["chart_type"] = None
        
        # Code cleaning: Remove markdown code blocks (basic cleaning only)
        # AST post-processor will handle more complex fixes
        
        logger.info(f"Generated code ({'Python' if needs_chart else 'SQL'}): {code[:100]}...")
        state["code"] = code
        return state
        
    except Exception as e:
        logger.error(f"Error in Agent A2: {str(e)}")
        state["code"] = None
        return state


def agent_a4_executor(state: GraphState) -> GraphState:
    """
    Agent A4: Executor
    Executes SQL or Python code and returns results.
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with result field populated
    """
    logger.info("Agent A4 (Executor): Executing code...")
    
    # If result is already a helpful guidance message (from A1 for vague queries), skip execution
    current_result = state.get("result")
    if current_result and isinstance(current_result, str) and ("Could you be more specific" in current_result or "I'd be happy to help" in current_result):
        logger.info("Skipping code execution - helpful guidance message already set")
        return state
    
    code = state.get("code")
    if not code:
        logger.warning("No code to execute")
        state["result"] = None
        return state
    
    # CRITICAL: Use code_type from state instead of recalculating from VIZ_CONFIG
    # This prevents Python code from being executed as SQL
    code_type = state.get("code_type", "sql")  # Default to SQL for safety
    
    # Safety check: detect if code is Python (has imports) or SQL
    if code and ("import " in code or "from " in code):
        # This is Python code, not SQL
        needs_chart = True
        logger.warning("Detected Python code in SQL path - switching to Python execution")
        state["code_type"] = "python"  # Update state
    elif code_type == "python":
        needs_chart = True
    else:
        needs_chart = False
    
    try:
        if needs_chart:
            # Execute Python code for charting using PythonREPLTool (as required by assignment)
            from pathlib import Path
            import sys
            import io
            import pickle
            import tempfile
            
            # Get Python REPL tool (LangChain PythonREPLTool)
            python_repl = get_python_repl()
            
            # Add database path context and necessary imports
            db_path = Path(__file__).parent.parent / "robot_vacuum.db"
            
            # Create temporary file paths for storing the figure and DataFrame objects
            temp_dir = Path(tempfile.gettempdir())
            state_id = id(state)
            figure_pickle_path = temp_dir / f"figure_{state_id}.pkl"
            df_pickle_path = temp_dir / f"df_{state_id}.pkl"
            
            # Modify code to save figure and DataFrame to pickle files after creation
            # This allows us to retrieve the objects after REPL execution
            code_with_save = f"""
import sys
import os
from pathlib import Path
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import pickle

# Set working directory
os.chdir(r'{Path(__file__).parent.parent.absolute()}')

{code}

# Save figure to pickle file for retrieval after REPL execution
if 'figure' in locals():
    figure_obj = locals()['figure']
elif 'figure' in globals():
    figure_obj = globals()['figure']
else:
    figure_obj = None

if figure_obj is not None:
    with open(r'{figure_pickle_path}', 'wb') as f:
        pickle.dump(figure_obj, f)
    print("Figure saved successfully")
else:
    print("Warning: figure variable not found")

# Save DataFrame to pickle file if it exists (for explainability)
if 'df' in locals():
    df_obj = locals()['df']
elif 'df' in globals():
    df_obj = globals()['df']
else:
    df_obj = None

if df_obj is not None:
    with open(r'{df_pickle_path}', 'wb') as f:
        pickle.dump(df_obj, f)
    print("DataFrame saved successfully")
else:
    print("Warning: df variable not found")
"""
            
            # Validate Python syntax before execution
            try:
                compile(code_with_save, '<string>', 'exec')
            except SyntaxError as syn_err:
                logger.error(f"Syntax error in generated Python code: {syn_err}")
                logger.error(f"Problematic code:\n{code[:500]}")
                state["result"] = f"Execution error: invalid syntax at line {syn_err.lineno}: {syn_err.msg}"
                state["visuals"] = None
                return state
            
            # Execute code using PythonREPLTool (as required by assignment)
            try:
                # Use LangChain PythonREPLTool to execute the code
                output = python_repl.run(code_with_save)
                logger.info(f"PythonREPLTool execution output: {output[:200] if output else 'No output'}...")
                
                # Retrieve figure from pickle file
                figure = None
                if figure_pickle_path.exists():
                    try:
                        with open(figure_pickle_path, 'rb') as f:
                            figure = pickle.load(f)
                        logger.info("Figure successfully loaded from pickle file")
                        # Clean up pickle file
                        figure_pickle_path.unlink()
                    except Exception as pickle_err:
                        logger.error(f"Error loading figure from pickle: {str(pickle_err)}")
                else:
                    logger.warning("Figure pickle file not found after REPL execution")
                
                # Retrieve DataFrame from pickle file if available (for explainability)
                df = None
                if df_pickle_path.exists():
                    try:
                        with open(df_pickle_path, 'rb') as f:
                            df = pickle.load(f)
                        logger.info("DataFrame successfully loaded from pickle file")
                        # Clean up pickle file
                        df_pickle_path.unlink()
                    except Exception as pickle_err:
                        logger.error(f"Error loading DataFrame from pickle: {str(pickle_err)}")
                
                if figure is not None:
                    state["visuals"] = figure
                    state["result"] = "Chart generated successfully"
                    logger.info("Chart generated successfully")
                    
                    # Store DataFrame if available (for explainability)
                    if df is not None:
                        # Convert to pandas DataFrame if it's not already
                        import pandas as pd
                        if not isinstance(df, pd.DataFrame):
                            try:
                                df = pd.DataFrame(df)
                            except:
                                df = None
                        state["sql_result_df"] = df
                        logger.info(f"Captured DataFrame with {len(df) if df is not None else 0} rows for explainability")
                    else:
                        state["sql_result_df"] = None
                        logger.info("DataFrame not available (this is okay)")
                    
                    # Preserve code metadata for explainability (if not already set)
                    if not state.get("python_code"):
                        state["python_code"] = code
                    if not state.get("sql_query"):
                        # Try to extract SQL from Python code if not already extracted
                        import re
                        # Try multiple patterns
                        sql_match = re.search(r"pd\.read_sql_query\(['\"](.*?)['\"]", code, re.DOTALL)
                        if not sql_match:
                            sql_match = re.search(r"conn\.execute\(['\"](.*?)['\"]", code, re.DOTALL)
                        if not sql_match:
                            sql_match = re.search(r"cursor\.execute\(['\"](.*?)['\"]", code, re.DOTALL)
                        if not sql_match:
                            sql_match = re.search(r"query\s*=\s*['\"]{3}(.*?)['\"]{3}", code, re.DOTALL)
                        if sql_match:
                            state["sql_query"] = sql_match.group(1).strip()
                else:
                    state["result"] = "Chart code executed but no figure variable found"
                    state["visuals"] = None
                    logger.warning("No figure variable found after execution")
            except Exception as exec_error:
                logger.error(f"Error executing Python code: {str(exec_error)}")
                state["result"] = f"Execution error: {str(exec_error)}"
                state["visuals"] = None
                
        else:
            # Execute SQL query
            query_lower = state.get("query", "").lower()
            
            # Debug logging for manufacturer ratings queries
            if "rating" in query_lower and "manufacturer" in query_lower:
                logger.info(f"[RATINGS DEBUG] Generated SQL for manufacturer ratings:")
                logger.info(f"[RATINGS DEBUG] {code[:500]}")
                # Check if GROUP BY is present
                if "GROUP BY" not in code.upper():
                    logger.error("[RATINGS DEBUG] WARNING: Missing GROUP BY in manufacturer ratings query!")
                else:
                    logger.info("[RATINGS DEBUG] GROUP BY clause found in query")
            
            sql_db = get_sql_db()
            result_str = sql_db.run(code)
            
            # Extract column names from SQL query for DataFrame creation
            column_names = extract_column_names_from_sql(code)
            state["column_names"] = column_names if column_names else None
            
            # Preserve SQL query for explainability (if not already set)
            if not state.get("sql_query"):
                state["sql_query"] = code
            
            # Convert SQL result string to DataFrame immediately
            # This avoids parsing issues in the UI layer
            try:
                import ast
                import pandas as pd
                
                # Parse the string representation of results
                if isinstance(result_str, str) and result_str.strip().startswith("[") and "(" in result_str:
                    parsed_result = ast.literal_eval(result_str)
                    if isinstance(parsed_result, list) and len(parsed_result) > 0:
                        # Convert to DataFrame
                        if isinstance(parsed_result[0], (list, tuple)):
                            if column_names and len(column_names) == len(parsed_result[0]):
                                # Handle duplicate column names by appending suffixes
                                seen = {}
                                unique_column_names = []
                                for col_name in column_names:
                                    if col_name in seen:
                                        seen[col_name] += 1
                                        unique_col_name = f"{col_name}_{seen[col_name]}"
                                    else:
                                        seen[col_name] = 0
                                        unique_col_name = col_name
                                    unique_column_names.append(unique_col_name)
                                
                                # Use extracted column names (with duplicates handled)
                                df = pd.DataFrame(parsed_result, columns=unique_column_names)
                                logger.info(f"Converted SQL result to DataFrame with {len(df)} rows and columns: {unique_column_names}")
                            else:
                                # Fallback to generic names
                                df = pd.DataFrame(parsed_result)
                                logger.warning(f"Column names mismatch or unavailable. Expected {len(parsed_result[0]) if parsed_result else 0} columns, got {len(column_names) if column_names else 0}")
                        else:
                            # Single column result
                            col_name = column_names[0] if column_names and len(column_names) > 0 else "Value"
                            df = pd.DataFrame(parsed_result, columns=[col_name])
                        
                        # Store DataFrame instead of string
                        state["result"] = df
                        logger.info(f"SQL result converted to DataFrame: {len(df)} rows, {len(df.columns)} columns")
                    else:
                        # Empty result
                        state["result"] = pd.DataFrame()
                        logger.info("SQL query returned empty result")
                else:
                    # Result is not in expected format, store as string
                    state["result"] = result_str
                    logger.warning(f"SQL result not in expected format (list of tuples), storing as string")
            except (ValueError, SyntaxError) as parse_error:
                # If parsing fails, store as string and let UI handle it
                logger.warning(f"Could not parse SQL result to DataFrame: {str(parse_error)}. Storing as string.")
                state["result"] = result_str
            except Exception as e:
                # Any other error, store as string
                logger.error(f"Error converting SQL result to DataFrame: {str(e)}. Storing as string.")
                state["result"] = result_str
            
            state["visuals"] = None
        
        # Merge A5 Presenter logic: Format output based on VIZ_CONFIG
        # Enforce single output mode (chart OR table, not both)
        intent_str = state.get("intent", "GENERAL_QUERY")
        intent = Intent(intent_str)
        viz_config = VIZ_CONFIG.get(intent, {"mode": "table"})
        output_mode = viz_config.get("mode", "table")
        
        if output_mode == "chart":
            # Chart mode: keep visuals, set result to summary
            if state.get("visuals") is not None:
                state["result"] = "Chart generated successfully"
            else:
                # No chart generated, keep result as fallback
                state["visuals"] = None
        else:
            # Table mode: keep result, clear visuals
            state["visuals"] = None
        
        logger.info(f"Code execution completed. Output mode: {output_mode}, has_visuals: {state.get('visuals') is not None}, has_result: {state.get('result') is not None}")
        return state
        
    except Exception as e:
        logger.error(f"Error in Agent A4: {str(e)}")
        state["result"] = f"Execution error: {str(e)}"
        state["visuals"] = None
        return state


