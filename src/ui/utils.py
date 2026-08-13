"""
Utility functions for UI formatting and error handling.
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def format_result_for_display(result):
    """
    Format result for conversational text display.
    Returns conversational text only (no references to separate panels).
    
    Args:
        result: The result from the agent (can be str, list, tuple, DataFrame, or None)
        
    Returns:
        str: Formatted conversational message
    """
    if result is None:
        return "I couldn't retrieve any results for that query."
    
    if isinstance(result, str):
        if "error" in result.lower() or "execution error" in result.lower():
            return f"I encountered an error: {result}"
        if "Chart generated successfully" in result:
            return "I've generated a chart for you below."
        
        # If it's a SQL result string (list of tuples), don't show raw string
        # The table will be rendered by render_message_artifacts()
        if result.strip().startswith("[") and "(" in result:
            try:
                import ast
                parsed_result = ast.literal_eval(result)
                if isinstance(parsed_result, list) and len(parsed_result) > 0:
                    # Return conversational message instead of raw string
                    return f"I found {len(parsed_result)} results. See the table below for details."
            except (ValueError, SyntaxError):
                pass  # If parsing fails, fall through to return result
        
        return result
    
    if isinstance(result, (list, tuple)):
        if len(result) == 1 and isinstance(result[0], (list, tuple)):
            # Single value result like [(3771,)]
            value = result[0][0] if result[0] else "N/A"
            return f"The result is: {value}"
        return f"I found {len(result)} results. See the table below for details."
    
    if isinstance(result, pd.DataFrame):
        return f"I found {len(result)} rows of data. See the table below for details."
    
    return "I've processed your query. See the results below."


def format_error_message(error: Exception) -> str:
    """
    Format error message with context-aware user-friendly messages.
    
    Args:
        error: The exception that occurred
        
    Returns:
        str: User-friendly error message
    """
    error_str = str(error).lower()
    
    # Context-aware error messages
    if "timeout" in error_str or "timed out" in error_str:
        return "⏱️ The query took too long to process. Try a simpler question or be more specific."
    elif "api" in error_str and "key" in error_str:
        return "🔑 API key issue detected. Please check your OpenAI API key configuration."
    elif "database" in error_str or "sql" in error_str:
        return f"💾 Database error: {str(error)[:100]}. Please ensure the database is properly initialized."
    elif "syntax" in error_str or "parse" in error_str:
        return "📝 I had trouble understanding your query. Could you rephrase it more clearly?"
    else:
        # Generic but friendly error
        return f"❌ I encountered an issue: {str(error)[:150]}. Please try rephrasing your question."

