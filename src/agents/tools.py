"""
Tools for the agent system: SQL Database, Schema Introspection, and Python REPL.
"""
import os
import logging
from typing import Dict, List
from sqlalchemy import create_engine, inspect, text
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv

# PythonREPLTool import - try different locations
try:
    from langchain_community.tools import PythonREPLTool
except ImportError:
    try:
        from langchain_experimental.tools import PythonREPLTool
    except ImportError:
        # Fallback: Create a simple wrapper
        class PythonREPLTool:
            def run(self, code: str) -> str:
                import io
                import sys
                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                try:
                    exec(code)
                    output = buffer.getvalue()
                    return output
                finally:
                    sys.stdout = old_stdout

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def get_database_url() -> str:
    """Get database URL from .env or default to SQLite."""
    from pathlib import Path
    
    db_url = os.getenv("DATABASE_URL", "sqlite:///robot_vacuum.db")
    
    # Always use absolute path for SQLite
    if db_url.startswith("sqlite:///"):
        # Extract the database file path
        db_file = db_url.replace("sqlite:///", "")
        
        # If it's already an absolute path (starts with / or drive letter), use it
        if os.path.isabs(db_file):
            db_path = Path(db_file)
        else:
            # Compute absolute path relative to src directory
            # tools.py is in src/agents/, so go up two levels to src/
            src_dir = Path(__file__).parent.parent
            db_path = src_dir / db_file
        
        # Ensure absolute path
        db_path = db_path.resolve()
        db_url = f"sqlite:///{db_path}"
    
    logger.info(f"Database URL: {db_url}")
    logger.info(f"Database absolute path: {db_path if 'db_path' in locals() else 'N/A'}")
    return db_url


def get_db_schema() -> str:
    """
    Get a simplified string representation of the database schema.
    This is used for Schema Injection into the Agent's system prompt.
    
    Returns:
        String representation of table schemas (Table Names + Column Names + Types)
    """
    db_url = get_database_url()
    engine = create_engine(db_url)
    inspector = inspect(engine)
    
    schema_parts = []
    schema_parts.append("=== Database Schema ===\n")
    
    # Get all table names
    table_names = inspector.get_table_names()
    
    # SQLite reserved keywords that need quoting
    reserved_keywords = {'order', 'group', 'select', 'table', 'index', 'view'}
    
    for table_name in sorted(table_names):
        # Quote table name if it's a reserved keyword
        quoted_table = f'"{table_name}"' if table_name.lower() in reserved_keywords else table_name
        schema_parts.append(f"\nTable: {quoted_table} (actual name: {table_name})")
        schema_parts.append("-" * (len(table_name) + 8))
        
        # Get columns for this table
        columns = inspector.get_columns(table_name)
        for col in columns:
            col_name = col['name']
            col_type = str(col['type'])
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            schema_parts.append(f"  {col_name}: {col_type} ({nullable})")
        
        # Get foreign keys
        foreign_keys = inspector.get_foreign_keys(table_name)
        if foreign_keys:
            schema_parts.append("\n  Foreign Keys:")
            for fk in foreign_keys:
                constrained_cols = ", ".join(fk['constrained_columns'])
                referred_table = fk['referred_table']
                referred_cols = ", ".join(fk['referred_columns'])
                schema_parts.append(f"    {constrained_cols} -> {referred_table}({referred_cols})")
        
        # Get primary keys
        pk_constraint = inspector.get_pk_constraint(table_name)
        if pk_constraint and pk_constraint['constrained_columns']:
            pk_cols = ", ".join(pk_constraint['constrained_columns'])
            schema_parts.append(f"\n  Primary Key: {pk_cols}")
    
    schema_str = "\n".join(schema_parts)
    logger.info("Schema introspection completed")
    return schema_str


def get_sql_database() -> SQLDatabase:
    """
    Initialize and return SQLDatabase instance for LangChain.
    
    Returns:
        SQLDatabase instance connected to robot_vacuum.db
    """
    db_url = get_database_url()
    db = SQLDatabase.from_uri(db_url)
    logger.info("SQLDatabase initialized")
    return db


def get_python_repl_tool() -> PythonREPLTool:
    """
    Initialize and return PythonREPLTool for executing Python code (charting).
    
    Returns:
        PythonREPLTool instance
    """
    tool = PythonREPLTool()
    logger.info("PythonREPLTool initialized")
    return tool


# Initialize tools at module level (singleton pattern)
_sql_db = None
_python_repl = None


def get_sql_db() -> SQLDatabase:
    """Get singleton SQLDatabase instance."""
    global _sql_db
    if _sql_db is None:
        _sql_db = get_sql_database()
    return _sql_db


def get_python_repl() -> PythonREPLTool:
    """Get singleton PythonREPLTool instance."""
    global _python_repl
    if _python_repl is None:
        _python_repl = get_python_repl_tool()
    return _python_repl


if __name__ == "__main__":
    # Test schema introspection
    schema = get_db_schema()
    print(schema)
    
    # Test SQL database
    db = get_sql_db()
    print(f"\nDatabase connected. Sample query:")
    result = db.run("SELECT COUNT(*) as total FROM \"order\"")
    print(f"Total orders: {result}")

