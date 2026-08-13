"""
Custom CSS styling for the Robot Vacuum Depot application.
"""
def get_custom_css() -> str:
    """
    Returns custom CSS for visual enhancements.
    
    Returns:
        str: CSS string to be injected via st.markdown()
    """
    return """
    <style>
        /* ============================================
           TYPOGRAPHY
           ============================================ */
        h1 {
            color: #1f2937;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        h2 {
            color: #374151;
            font-weight: 600;
            margin-top: 1rem;
            margin-bottom: 0.75rem;
        }

        h3 {
            color: #4b5563;
            font-weight: 600;
            margin-top: 1rem;
            margin-bottom: 0.75rem;
        }

        /* ============================================
           SIDEBAR BRANDING - LOGO/BRAND MARK
           ============================================ */
        .sidebar-branding {
            text-align: center;
            padding: 0.25rem 0 0.6rem 0;
            margin-bottom: 0.6rem;
            border-bottom: 2px solid #e5e7eb;
        }

        .sidebar-title {
            font-size: 2rem;
            font-weight: 800;
            color: #1f2937;
            margin: 0;
            letter-spacing: -0.01em;
            line-height: 1.2;
        }

        .sidebar-tagline {
            font-size: 0.9rem;
            color: #6b7280;
            margin: 0.25rem 0 0 0;
            font-weight: 400;
        }

        /* ============================================
           WELCOME SECTION - PROMINENT SESSION HEADER
           ============================================ */
        .welcome-section {
            margin: 0 0 1rem 0;
            padding-left: 1.5rem;
            border-left: 3px solid #667eea;
        }

        .welcome-heading {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1f2937;
            margin: 0 0 0.4rem 0;
            letter-spacing: -0.01em;
        }

        .welcome-text {
            font-size: 1.1rem;
            color: #4b5563;
            margin: 0;
        }

        /* ============================================
           CATEGORY SECTIONS
           ============================================ */
        .category-analytics {
            background: #e3f2fd;
            padding: 0.6rem;
            border-radius: 8px;
            margin-bottom: 0.6rem;
            border-left: 3px solid #2196f3;
        }

        .category-data {
            background: #e8f5e9;
            padding: 0.6rem;
            border-radius: 8px;
            margin-bottom: 0.6rem;
            border-left: 3px solid #4caf50;
        }

        .category-analytics h2,
        .category-data h2 {
            margin-top: 0;
            margin-bottom: 0.4rem;
        }
        
        /* Uniform button spacing within category sections */
        .category-analytics .stButton,
        .category-data .stButton {
            margin-bottom: 0.4rem;
        }
        
        .category-analytics .stButton:last-child,
        .category-data .stButton:last-child {
            margin-bottom: 0;
        }

        /* ============================================
           BUTTONS
           ============================================ */
        .stButton > button {
            border-radius: 8px;
            transition: all 0.3s ease;
            font-weight: 500;
            border: none;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
        }

        .stButton > button:active {
            transform: translateY(0);
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }

        /* ============================================
           SIDEBAR
           ============================================ */
        .sidebar .sidebar-content {
            padding: 1rem;
        }

        [data-testid="stSidebar"] {
            background-color: #fafafa;
            overflow-y: visible !important;
            height: 100vh !important;
        }

        [data-testid="stSidebar"] h2 {
            color: #1f2937;
            font-weight: 600;
            margin-top: 0;
            margin-bottom: 0.4rem;
        }

        [data-testid="stSidebar"] ul {
            margin-left: 1rem;
            margin-top: 0.2rem;
            margin-bottom: 0.2rem;
        }

        [data-testid="stSidebar"] li {
            margin-bottom: 0.12rem;
            color: #4b5563;
        }
        
        /* Reduce spacing around dividers in sidebar */
        [data-testid="stSidebar"] hr {
            margin-top: 0.4rem;
            margin-bottom: 0.4rem;
        }
        
        /* Sidebar - remove top padding to eliminate empty space */
        [data-testid="stSidebar"] .sidebar-branding {
            padding-top: 0;
            margin-top: 0;
        }
        
        /* Sidebar content container - prevent scrolling */
        [data-testid="stSidebar"] > div {
            overflow-y: visible !important;
        }

        /* ============================================
           SPACING & LAYOUT
           ============================================ */
        /* Main area - minimal top padding for clean chat interface */
        .main .block-container {
            padding-top: 0.5rem;
            padding-bottom: 0rem;
        }
        
        /* Uniform spacing for all subheaders on landing page */
        .main h2,
        .main h3 {
            margin-top: 0.6rem;
            margin-bottom: 0.4rem;
        }
        
        /* Consistent spacing between sections */
        .main > div > div {
            margin-bottom: 0.6rem;
        }

        /* ============================================
           RESPONSIVE DESIGN
           ============================================ */
        @media (max-width: 768px) {
            .sidebar-title {
                font-size: 1.75rem;
            }

            .sidebar-tagline {
                font-size: 0.85rem;
            }

            .welcome-section {
                padding-left: 1rem;
            }

            .welcome-heading {
                font-size: 2rem;
            }
        }

        /* ============================================
           CHAT MESSAGES
           ============================================ */
        .stChatMessage {
            padding: 1rem;
        }

        /* ============================================
           EXPANDERS
           ============================================ */
        .streamlit-expanderHeader {
            font-weight: 500;
            color: #667eea;
        }

        /* ============================================
           SUCCESS/INFO MESSAGES
           ============================================ */
        .stSuccess {
            border-radius: 8px;
        }

        .stInfo {
            border-radius: 8px;
        }
    </style>
    """

