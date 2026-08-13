"""
Streamlit UI for Robot Vacuum Depot - Assignment 3
Modern ChatGPT-style single-column interface with inline persistent artifacts
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import logging

# Add src to path for imports
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from agents.graph import graph
from agents.state import GraphState
from ui.styles import get_custom_css
from ui.components import render_message_artifacts
from ui.utils import format_result_for_display, format_error_message

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Robot Vacuum Depot - AI Assistant",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "graph_app" not in st.session_state:
    st.session_state.graph_app = graph
    logger.info("Graph initialized in session state")


def main():
    """Main Streamlit application."""
    
    # Load custom CSS
    st.markdown(get_custom_css(), unsafe_allow_html=True)
    
    # ============================================
    # SIDEBAR: BRANDING & CONTROLS
    # ============================================
    with st.sidebar:
        # Branding - Logo/Brand Mark
        st.markdown("""
        <div class="sidebar-branding">
            <h1 class="sidebar-title">🤖 Robot Vacuum Depot</h1>
            <p class="sidebar-tagline">AI-Powered Data Analytics Assistant</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.header("📊 About")
        st.markdown("""
        This AI assistant can answer questions about:
        - Order statistics and trends
        - Delivery status distributions
        - Warehouse inventory levels
        - Customer reviews and ratings
        - Shipping costs and carriers
        - And much more!
        """)
        st.markdown("---")
        
        # Reset Chat button
        if st.button("🔄 Reset Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    
    # ============================================
    # MAIN AREA: CONDITIONAL WELCOME (Hero State)
    # ============================================
    # Only show when messages is empty (ChatGPT-style)
    if len(st.session_state.messages) == 0:
        # Welcome Section - Prominent Session Header
        st.markdown("""
        <div class="welcome-section">
            <h1 class="welcome-heading">👋 Welcome</h1>
            <p class="welcome-text">Try asking a question, or use one of these starter queries:</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Analytics Queries (Charts) - Color-coded category
        st.markdown('<div class="category-analytics">', unsafe_allow_html=True)
        st.subheader("📊 Analytics & Visualizations")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📈 Monthly revenue trends", use_container_width=True):
                st.session_state.example_query = "Show me the monthly revenue trends over time"
                st.rerun()
        with col2:
            if st.button("📊 Delivery status distribution", use_container_width=True):
                st.session_state.example_query = "Show me the distribution of delivery statuses"
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Data Queries (Tables) - Color-coded category
        st.markdown('<div class="category-data">', unsafe_allow_html=True)
        st.subheader("📋 Data & Reports")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📦 Warehouses below restock", use_container_width=True):
                st.session_state.example_query = "Which warehouses have products below their restock threshold?"
                st.rerun()
            if st.button("⭐ Best manufacturer by review", use_container_width=True):
                st.session_state.example_query = "Which manufacturer has the best average review rating?"
                st.rerun()
        with col2:
            if st.button("📊 Total orders count", use_container_width=True):
                st.session_state.example_query = "How many orders are there?"
                st.rerun()
            if st.button("🚚 Shipping costs by carrier", use_container_width=True):
                st.session_state.example_query = "Compare the average shipping costs by carrier"
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ============================================
    # MAIN AREA: DYNAMIC CHAT FEED
    # ============================================
    
    # Display chat history with inline artifacts
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            # Display text content
            st.write(message["content"])
            
            # Render inline artifacts (charts/tables) with unique keys
            render_message_artifacts(message, message_index=idx)
    
    # Handle example query from welcome screen
    user_input = None
    if "example_query" in st.session_state:
        user_input = st.session_state.example_query
        del st.session_state.example_query
    
    # Chat input
    if user_input is None:
        user_input = st.chat_input("Ask a question about the data...")
    
    if user_input:
        # No need to append preference - users can specify in their query naturally
        user_input_with_pref = user_input
        
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Display user message immediately
        with st.chat_message("user"):
            st.write(user_input)
        
        # Show processing spinner
        with st.spinner("Processing your query..."):
            try:
                # Initialize graph state
                initial_state: GraphState = {
                    "query": user_input_with_pref,
                    "plan": None,
                    "code": None,
                    "result": None,
                    "visuals": None,
                    "message_history": st.session_state.messages.copy(),
                    "intent": None,
                    "column_names": None,
                    "code_type": None,
                    "sql_query": None,
                    "python_code": None,
                    "chart_type": None,
                    "sql_result_df": None
                }
                
                # Execute graph
                logger.info(f"Executing query: {user_input}")
                final_state = st.session_state.graph_app.invoke(initial_state)
                
                # Format result for conversational display
                chat_response = format_result_for_display(final_state.get("result"))
                
                # Add assistant response with complete payload (including visuals, result, column_names, and code metadata)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": chat_response,
                    "visuals": final_state.get("visuals"),  # Can be None
                    "result": final_state.get("result"),  # Can be None
                    "column_names": final_state.get("column_names"),  # For DataFrame column names
                    "intent": final_state.get("intent"),  # For chart key generation
                    "sql_query": final_state.get("sql_query"),  # For technical details expander
                    "python_code": final_state.get("python_code"),  # For technical details expander (kept for debugging if needed)
                    "chart_type": final_state.get("chart_type"),  # For technical details expander
                    "sql_result_df": final_state.get("sql_result_df")  # DataFrame from SQL query (for chart explainability)
                })
                
                logger.info("Query processed successfully")
                
                # Add success indicator
                if final_state.get("visuals") is not None:
                    st.success("✅ Chart generated successfully!")
                elif final_state.get("result") is not None:
                    # Check if result is meaningful (not just "Chart generated successfully")
                    result = final_state.get("result")
                    if isinstance(result, (list, tuple, pd.DataFrame)) or (
                        isinstance(result, str) and 
                        result != "Chart generated successfully" and
                        "error" not in result.lower()
                    ):
                        st.success("✅ Query processed successfully!")
                
            except Exception as e:
                # Use centralized error formatting
                error_msg = format_error_message(e)
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                    "visuals": None,
                    "result": None,
                    "column_names": None,
                    "intent": None,
                    "sql_query": None,
                    "python_code": None,
                    "chart_type": None,
                    "sql_result_df": None
                })
                logger.error(f"Error processing query: {str(e)}", exc_info=True)
        
        # Rerun to update display with new message
        st.rerun()


if __name__ == "__main__":
    main()
