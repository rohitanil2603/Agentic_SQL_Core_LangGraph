"""
Post-Processor Agent: Uses AST transformation to fix generated code reliably.
Replaces regex-based fixes with deterministic AST transformations.
"""
import logging
from agents.state import GraphState
from agents.ast_transformer import (
    fix_python_code_with_ast,
    fix_sql_code,
    SecurityValidator
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def agent_a3_post_processor(state: GraphState) -> GraphState:
    """
    Agent A3: Post-Processor
    Uses AST transformation to fix common issues in generated code.
    
    This agent:
    - Fixes datetime conversion issues in Python code (monthly revenue)
    - Validates and fixes SQL reserved keywords
    - Performs security validation on SQL queries
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with fixed code
    """
    logger.info("Agent A3 (Post-Processor): Processing code with AST transformation...")
    
    # If result is already a helpful guidance message (from A1 for vague queries), skip processing
    current_result = state.get("result")
    if current_result and isinstance(current_result, str) and ("Could you be more specific" in current_result or "I'd be happy to help" in current_result):
        logger.info("Skipping post-processing - helpful guidance message already set")
        return state
    
    code = state.get("code")
    code_type = state.get("code_type", "sql")
    query = state.get("query", "").lower()
    intent = state.get("intent", "")
    
    if not code:
        logger.warning("No code to post-process")
        return state
    
    try:
        if code_type == "python":
            # Fix Python code using AST transformation
            # Check if this is a monthly revenue query from query or intent
            # Be more aggressive in detection
            query_lower = query.lower()
            code_lower = code.lower()
            is_monthly_revenue = (
                ('month' in query_lower and ('revenue' in query_lower or 'trend' in query_lower)) or
                intent == "REVENUE_TRENDS" or
                ('month' in code_lower and ('revenue' in code_lower or 'strftime' in code_lower or 
                  'monthly' in code_lower or 'trend' in code_lower)) or
                ('strftime' in code_lower and '%Y-%m' in code_lower and 'month' in code_lower)
            )
            
            if is_monthly_revenue:
                logger.info("Detected monthly revenue query - applying AST fixes")
            else:
                logger.info("Applying AST transformation to Python code")
            
            fixed_code = fix_python_code_with_ast(code)
            
            if fixed_code != code:
                logger.info("Code was modified by AST transformer")
                state["code"] = fixed_code
                # Also update python_code field for explainability
                if state.get("python_code"):
                    state["python_code"] = fixed_code
            else:
                logger.info("No changes needed in Python code")
        
        elif code_type == "sql":
            # Fix SQL code
            logger.info("Applying SQL fixes and validation")
            fixed_sql, error = fix_sql_code(code)
            
            if error:
                # Security violation detected
                logger.error(f"Security validation failed: {error}")
                state["code"] = None
                state["result"] = error
                return state
            
            if fixed_sql != code:
                logger.info("SQL code was modified")
                state["code"] = fixed_sql
                # Also update sql_query field for explainability
                if state.get("sql_query"):
                    state["sql_query"] = fixed_sql
            else:
                logger.info("No changes needed in SQL code")
        
        logger.info("Post-processing completed successfully")
        return state
        
    except Exception as e:
        logger.error(f"Error in post-processor: {str(e)}")
        # Don't fail silently - return original code
        logger.warning("Post-processing failed, using original code")
        return state

