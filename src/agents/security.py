"""
Security utilities for code validation.
Centralizes dangerous pattern detection for SQL and Python code.
"""
import logging
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Dangerous patterns that should be rejected
DANGEROUS_SQL_PATTERNS = [
    "DROP",
    "DELETE",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "INSERT",
    "UPDATE"
]

DANGEROUS_PYTHON_PATTERNS = [
    "__import__",
    "eval(",
    "exec(",
    "open(",
    "file(",
]


def validate_sql_security(sql_code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate SQL code for dangerous patterns.
    
    Args:
        sql_code: SQL code string to validate
        
    Returns:
        Tuple of (is_safe, error_message)
        - is_safe: True if code is safe, False if dangerous pattern detected
        - error_message: Error message if unsafe, None if safe
    """
    if not sql_code:
        return True, None
    
    sql_upper = sql_code.upper()
    
    for pattern in DANGEROUS_SQL_PATTERNS:
        # Check for pattern followed by TABLE or FROM (more specific matching)
        if pattern in sql_upper:
            if f"{pattern} TABLE" in sql_upper or f"{pattern} FROM" in sql_upper:
                logger.error(f"Dangerous SQL pattern detected: {pattern} - Rejecting for safety")
                return False, f"Security: Destructive database operations ({pattern}) are not allowed. Only SELECT queries are permitted."
    
    return True, None


def validate_python_security(python_code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Python code for dangerous patterns.
    
    Args:
        python_code: Python code string to validate
        
    Returns:
        Tuple of (is_safe, error_message)
        - is_safe: True if code is safe, False if dangerous pattern detected
        - error_message: Error message if unsafe, None if safe
    """
    if not python_code:
        return True, None
    
    code_upper = python_code.upper()
    
    for pattern in DANGEROUS_PYTHON_PATTERNS:
        if pattern in code_upper:
            logger.error(f"Dangerous Python pattern detected: {pattern} - Rejecting code for safety")
            return False, f"Security: The generated code contains a dangerous operation ({pattern}). Only SELECT queries and safe plotting code are allowed."
    
    return True, None

