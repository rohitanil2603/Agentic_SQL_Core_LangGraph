"""
UI module for Robot Vacuum Depot application.
Contains styling, components, and utility functions for the Streamlit interface.
"""

from ui.styles import get_custom_css
from ui.components import render_message_artifacts
from ui.utils import format_result_for_display, format_error_message

__all__ = [
    'get_custom_css',
    'render_message_artifacts',
    'format_result_for_display',
    'format_error_message'
]

