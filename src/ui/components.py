"""
UI components for rendering message artifacts (charts, tables, etc.).
"""
import streamlit as st
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def render_message_artifacts(message, message_index: int = 0):
    """
    Render visuals and results inline within a message bubble.
    Includes Technical Details expander for explainability.
    
    Args:
        message: Message dictionary with content, visuals, result, etc.
        message_index: Index of message in history (for unique chart keys)
    """
    # Render Plotly chart if present
    if message.get("visuals") is not None:
        try:
            # Generate unique key for chart to avoid Streamlit ID conflicts
            intent = message.get("intent", "unknown")
            chart_key = f"chart_{message_index}_{intent}_{hash(str(message.get('code', ''))[:50])}"
            st.plotly_chart(
                message["visuals"], 
                use_container_width=True,
                key=chart_key
            )
            logger.info(f"Chart rendered inline with key: {chart_key}")
            
            # Scenario A: Technical Details Expander for Charts
            sql_query = message.get("sql_query")
            sql_result_df = message.get("sql_result_df")
            chart_type = message.get("chart_type")
            
            if sql_query or sql_result_df is not None:
                with st.expander("🔍 View Logic: SQL & Data"):
                    if chart_type:
                        st.caption(f"**Chart Type:** {chart_type.title()}")
                    
                    if sql_query:
                        st.markdown("**Generated SQL:**")
                        st.code(sql_query, language='sql')
                    
                    # Show SQL query results as table instead of Python code
                    if sql_result_df is not None:
                        st.markdown("**SQL Query Results:**")
                        st.dataframe(sql_result_df, use_container_width=True)
                        st.caption(f"Query returned {len(sql_result_df)} rows")
                    elif sql_query:
                        # If we have SQL but no DataFrame, show a note
                        st.info("Data table not available for this chart.")
        except Exception as e:
            st.error(f"Error rendering chart: {str(e)}")
            logger.error(f"Chart rendering error: {str(e)}")
    
    # Render table/dataframe if present
    result = message.get("result")
    if result is not None:
        try:
            if isinstance(result, pd.DataFrame):
                st.dataframe(result, use_container_width=True)
                logger.info("DataFrame rendered inline")
            elif isinstance(result, (list, tuple)):
                if len(result) > 0:
                    if isinstance(result[0], (list, tuple)):
                        # List of rows - convert to DataFrame
                        try:
                            df = pd.DataFrame(result)
                            st.dataframe(df, use_container_width=True)
                            logger.info("List converted to DataFrame and rendered")
                        except Exception as e:
                            st.write(result)
                            logger.warning(f"Could not convert list to DataFrame: {str(e)}")
                    else:
                        # Simple list
                        st.write(result)
                else:
                    st.info("Empty result set.")
            elif isinstance(result, str):
                # SQLDatabase.run() returns string representation of results
                # Try to parse it into a DataFrame
                if result.strip().startswith("[") and "(" in result:
                    try:
                        import ast
                        # Parse the string representation of list of tuples
                        parsed_result = ast.literal_eval(result)
                        if isinstance(parsed_result, list) and len(parsed_result) > 0:
                            # Get column names from message if available
                            column_names = message.get("column_names")
                            
                            # Convert to DataFrame
                            if isinstance(parsed_result[0], (list, tuple)):
                                if column_names and len(column_names) == len(parsed_result[0]):
                                    # Use extracted column names
                                    df = pd.DataFrame(parsed_result, columns=column_names)
                                    logger.info(f"DataFrame created with column names: {column_names}")
                                else:
                                    # Fallback to generic names
                                    df = pd.DataFrame(parsed_result)
                                    logger.warning(f"Column names not available or mismatch, using generic names")
                                st.dataframe(df, use_container_width=True)
                                logger.info("String result parsed and converted to DataFrame")
                            else:
                                # Single column result
                                col_name = column_names[0] if column_names and len(column_names) > 0 else "Value"
                                df = pd.DataFrame(parsed_result, columns=[col_name])
                                st.dataframe(df, use_container_width=True)
                        else:
                            st.write(result)
                    except (ValueError, SyntaxError) as e:
                        # If parsing fails, check if it's an error message
                        if "error" in result.lower() or "execution error" in result.lower():
                            st.error(result)
                        else:
                            # Display as text if it's not parseable
                            st.write(result)
                        logger.warning(f"Could not parse string result: {str(e)}")
                elif "error" in result.lower() or "execution error" in result.lower():
                    st.error(result)
                else:
                    # Plain text result - don't display again since it's already in message["content"]
                    # Only display structured data (DataFrames, lists) that need rendering
                    pass
            else:
                st.write(result)
            
            # Scenario B: Technical Details Expander for Tables/Text
            # Only show if we have a result and no visuals (table/text output)
            if message.get("visuals") is None:
                sql_query = message.get("sql_query")
                
                if sql_query:
                    with st.expander("🔍 View Logic: Source SQL"):
                        st.code(sql_query, language='sql')
                        
                        # Show row count if result is a DataFrame
                        result = message.get("result")
                        if isinstance(result, pd.DataFrame):
                            st.caption(f"Query returned {len(result)} rows")
                        elif isinstance(result, (list, tuple)) and len(result) > 0:
                            if isinstance(result[0], (list, tuple)):
                                st.caption(f"Query returned {len(result)} rows")
                            else:
                                st.caption(f"Query returned {len(result)} result(s)")
        except Exception as e:
            st.error(f"Error rendering result: {str(e)}")
            logger.error(f"Result rendering error: {str(e)}")

