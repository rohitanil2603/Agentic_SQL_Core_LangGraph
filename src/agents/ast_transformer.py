"""
AST-based code transformers for post-processing generated code.
Provides reliable, deterministic fixes for common LLM code generation issues.
"""
import ast
import logging
import re
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DateTimeFixer(ast.NodeTransformer):
    """
    AST transformer that fixes datetime conversion issues in Python code.
    Specifically targets monthly revenue queries to ensure Month column remains as string.
    """
    
    def __init__(self):
        self.has_month_column = False
        self.has_string_conversion = False
        self.df_assign_node = None
        self.nodes_after_df = []
    
    def visit_Assign(self, node):
        """Track DataFrame assignments and check for Month column."""
        # Check if this is df = pd.read_sql_query(...)
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Attribute):
                if (isinstance(node.value.func.value, ast.Attribute) and
                    isinstance(node.value.func.value.value, ast.Name) and
                    node.value.func.value.value.id == 'pd' and
                    node.value.func.value.attr == 'read_sql_query'):
                    # Found df = pd.read_sql_query(...)
                    if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                        if node.targets[0].id == 'df':
                            self.df_assign_node = node
                            logger.info("Found df = pd.read_sql_query(...) assignment")
        
        # Check if this is df['Month'] = df['Month'].astype(str)
        if (len(node.targets) == 1 and 
            isinstance(node.targets[0], ast.Subscript) and
            isinstance(node.targets[0].value, ast.Name) and
            node.targets[0].value.id == 'df'):
            # Check if target is df['Month'] or df["Month"]
            if isinstance(node.targets[0].slice, ast.Constant):
                if node.targets[0].slice.value == 'Month':
                    # Check if value is df['Month'].astype(str)
                    if isinstance(node.value, ast.Call):
                        if (isinstance(node.value.func, ast.Attribute) and
                            node.value.func.attr == 'astype'):
                            if (isinstance(node.value.func.value, ast.Subscript) and
                                isinstance(node.value.func.value.value, ast.Name) and
                                node.value.func.value.value.id == 'df'):
                                self.has_string_conversion = True
                                logger.info("Found existing df['Month'] = df['Month'].astype(str)")
        
        # Check if Month column is referenced in the code
        if isinstance(node.value, ast.Call):
            # Check for pd.to_datetime(df['Month']) or similar
            if isinstance(node.value.func, ast.Attribute):
                if (isinstance(node.value.func.value, ast.Name) and
                    node.value.func.value.id == 'pd' and
                    node.value.func.attr == 'to_datetime'):
                    # Check if argument is df['Month']
                    if len(node.value.args) > 0:
                        arg = node.value.args[0]
                        if isinstance(arg, ast.Subscript):
                            if (isinstance(arg.value, ast.Name) and
                                arg.value.id == 'df' and
                                isinstance(arg.slice, ast.Constant) and
                                arg.slice.value == 'Month'):
                                # Found pd.to_datetime(df['Month']) - remove this call
                                logger.warning("Found pd.to_datetime(df['Month']) - will be removed")
                                # Return the argument directly (remove to_datetime call)
                                return ast.Assign(targets=node.targets, value=arg)
        
        return self.generic_visit(node)
    
    def visit_Call(self, node):
        """Remove pd.to_datetime() calls on Month column."""
        if isinstance(node.func, ast.Attribute):
            if (isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'pd' and
                node.func.attr == 'to_datetime'):
                # Check if argument is df['Month']
                if len(node.args) > 0:
                    arg = node.args[0]
                    if isinstance(arg, ast.Subscript):
                        if (isinstance(arg.value, ast.Name) and
                            arg.value.id == 'df' and
                            isinstance(arg.slice, ast.Constant) and
                            arg.slice.value == 'Month'):
                            # Replace pd.to_datetime(df['Month']) with just df['Month']
                            logger.info("Replacing pd.to_datetime(df['Month']) with df['Month']")
                            return arg
        return self.generic_visit(node)
    
    def fix_monthly_revenue_code(self, tree: ast.Module) -> ast.Module:
        """
        Main fix method: Ensures Month column is string type for monthly revenue queries.
        
        Args:
            tree: AST module to transform
            
        Returns:
            Transformed AST module
        """
        # First pass: Remove pd.to_datetime() calls and track df assignment
        tree = self.visit(tree)
        
        # Check if this is a monthly revenue query by looking for 'Month' in SQL or code
        # We'll check if Month column exists in the code
        code_str = ast.unparse(tree) if hasattr(ast, 'unparse') else str(tree)
        has_month_column = 'Month' in code_str or 'month' in code_str.lower()
        
        # Second pass: Check if we need to add string conversion
        if has_month_column and self.df_assign_node and not self.has_string_conversion:
            logger.info("Adding df['Month'] = df['Month'].astype(str) after pd.read_sql_query")
            
            # Find the df assignment in the tree
            for i, node in enumerate(tree.body):
                if isinstance(node, ast.Assign):
                    # Check if this is the df assignment we tracked
                    if (len(node.targets) == 1 and 
                        isinstance(node.targets[0], ast.Name) and
                        node.targets[0].id == 'df' and
                        isinstance(node.value, ast.Call) and
                        isinstance(node.value.func, ast.Attribute) and
                        isinstance(node.value.func.value, ast.Attribute) and
                        isinstance(node.value.func.value.value, ast.Name) and
                        node.value.func.value.value.id == 'pd' and
                        node.value.func.value.attr == 'read_sql_query'):
                        # Insert string conversion after df assignment
                        string_conversion = ast.parse("df['Month'] = df['Month'].astype(str)").body[0]
                        tree.body.insert(i + 1, string_conversion)
                        logger.info("Inserted string conversion after df assignment")
                        break
        
        return tree


class SQLKeywordFixer:
    """
    Utility class for fixing SQL reserved keyword issues.
    Ensures table/column names that are SQL reserved keywords are properly quoted.
    """
    
    SQLITE_RESERVED_KEYWORDS = {
        'order', 'group', 'select', 'from', 'where', 'join', 'inner', 'outer',
        'left', 'right', 'as', 'and', 'or', 'not', 'in', 'like', 'between',
        'is', 'null', 'case', 'when', 'then', 'else', 'end', 'having',
        'union', 'intersect', 'except', 'limit', 'offset', 'order', 'by'
    }
    
    @staticmethod
    def fix_reserved_keywords(sql: str) -> str:
        """
        Fix SQL reserved keywords by ensuring proper quoting.
        
        Args:
            sql: SQL query string
            
        Returns:
            Fixed SQL query with proper quoting
        """
        # This is a simple fix - if table name is "order", ensure it's quoted
        # More sophisticated fixes can be added if needed
        # For now, the LLM should already be generating quoted keywords
        # This is a safety net
        
        # Check if "order" table is used without quotes
        pattern = r'\bFROM\s+order\b'
        if re.search(pattern, sql, re.IGNORECASE):
            sql = re.sub(pattern, 'FROM "order"', sql, flags=re.IGNORECASE)
            logger.info("Fixed unquoted 'order' table name")
        
        return sql


class SecurityValidator:
    """
    Validates SQL code for security issues.
    Prevents SQL injection and destructive operations.
    """
    
    DANGEROUS_PATTERNS = [
        r'\bDROP\s+TABLE\b',
        r'\bDELETE\s+FROM\b',
        r'\bTRUNCATE\s+TABLE\b',
        r'\bALTER\s+TABLE\b',
        r'\bCREATE\s+TABLE\b',
        r'\bINSERT\s+INTO\b',
        r'\bUPDATE\s+.*\s+SET\b',
        r'\bEXEC\s*\(',
        r'\bEXECUTE\s*\(',
    ]
    
    @staticmethod
    def validate_sql(sql: str) -> tuple[bool, Optional[str]]:
        """
        Validate SQL for security issues.
        
        Args:
            sql: SQL query string
            
        Returns:
            Tuple of (is_safe, error_message)
        """
        sql_upper = sql.upper()
        
        for pattern in SecurityValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper):
                error_msg = f"Security: Dangerous SQL pattern detected: {pattern}"
                logger.error(error_msg)
                return False, error_msg
        
        # Ensure it starts with SELECT
        if not sql_upper.strip().startswith('SELECT'):
            error_msg = "Security: Only SELECT queries are allowed"
            logger.error(error_msg)
            return False, error_msg
        
        return True, None


def fix_python_code_with_ast(code: str) -> str:
    """
    Fix Python code using AST transformation.
    
    Args:
        code: Python code string
        
    Returns:
        Fixed Python code string
    """
    try:
        # Check if this is monthly revenue code - be more aggressive
        code_lower = code.lower()
        is_monthly_revenue = ('month' in code_lower and 
                             ('revenue' in code_lower or 'strftime' in code_lower or 
                              'monthly' in code_lower or 'trend' in code_lower))
        
        if not is_monthly_revenue:
            # Not a monthly revenue query, skip AST transformation
            logger.info("Not a monthly revenue query, skipping AST transformation")
            return code
        
        logger.info("Detected monthly revenue query - applying AST fixes")
        
        # Parse code to AST
        tree = ast.parse(code)
        
        # Apply DateTimeFixer
        fixer = DateTimeFixer()
        tree = fixer.fix_monthly_revenue_code(tree)
        
        # Convert AST back to code
        # Note: ast.unparse is available in Python 3.9+
        try:
            fixed_code = ast.unparse(tree)
            
            # CRITICAL: Always ensure string conversion for Month column in monthly revenue queries
            # This is a safety net - check if Month column exists and add conversion if missing
            has_month_column = ('Month' in fixed_code or 'month' in fixed_code.lower())
            has_string_conversion = ('astype(str)' in fixed_code or '.astype("str")' in fixed_code or 
                                    'astype(\'str\')' in fixed_code)
            
            if has_month_column and not has_string_conversion:
                logger.warning("Month column found but no string conversion - adding it")
                # Find df = pd.read_sql_query(...) pattern
                # Handle both single-line and multi-line SQL queries
                import re
                # Pattern 1: Single-line pd.read_sql_query
                pattern1 = r"(df\s*=\s*pd\.read_sql_query\([^)]+\))"
                match = re.search(pattern1, fixed_code, re.MULTILINE)

                found_multiline = False
                
                if not match:
                    # Pattern 2: Multi-line pd.read_sql_query with triple quotes or parentheses
                    # Match: df = pd.read_sql_query("""...""", conn) or df = pd.read_sql_query("...", conn)
                    pattern2 = r"(df\s*=\s*pd\.read_sql_query\s*\([^)]*(?:\([^)]*\)[^)]*)*\))"
                    match = re.search(pattern2, fixed_code, re.MULTILINE | re.DOTALL)
                
                if not match:
                    # Pattern 3: Find any line with df = pd.read_sql_query and match until the closing paren
                    # This handles multi-line SQL strings
                    lines = fixed_code.split('\n')
                   
                    for i, line in enumerate(lines):
                        if 'pd.read_sql_query' in line and 'df' in line:
                            # Find the end of this statement (could span multiple lines)
                            # Look for the closing paren that matches the opening
                            start_pos = fixed_code.find(line)
                            paren_count = line.count('(') - line.count(')')
                            current_pos = start_pos + len(line)
                            
                            # If not closed on this line, find the closing paren
                            if paren_count > 0:
                                while current_pos < len(fixed_code) and paren_count > 0:
                                    char = fixed_code[current_pos]
                                    if char == '(':
                                        paren_count += 1
                                    elif char == ')':
                                        paren_count -= 1
                                    current_pos += 1
                            
                            # Find the end of the line (or statement)
                            line_end = fixed_code.find('\n', current_pos)
                            if line_end == -1:
                                line_end = len(fixed_code)
                            
                            # Calculate indent
                            indent = len(line) - len(line.lstrip())
                            indent_str = ' ' * indent
                            
                            # Insert string conversion
                            fixed_code = fixed_code[:line_end] + f"\n{indent_str}df['Month'] = df['Month'].astype(str)" + fixed_code[line_end:]
                            logger.info("Added df['Month'] = df['Month'].astype(str) after pd.read_sql_query (multi-line)")
                            found_multiline = True
                            break
                
                # If regex match found (Pattern 1 or 2), use it
                if match and not found_multiline:
                    insert_pos = match.end()
                    # Get the line with df assignment
                    lines = fixed_code[:insert_pos].split('\n')
                    if lines:
                        last_line = lines[-1]
                        # Calculate indent from the df assignment line
                        indent = len(last_line) - len(last_line.lstrip())
                        indent_str = ' ' * indent
                        # Insert string conversion after df assignment
                        fixed_code = fixed_code[:insert_pos] + f"\n{indent_str}df['Month'] = df['Month'].astype(str)" + fixed_code[insert_pos:]
                        logger.info("Added df['Month'] = df['Month'].astype(str) after pd.read_sql_query")
                else:
                    # If pattern not found, try to add at the beginning after imports
                    # Find where df is first assigned
                    df_pattern = r"df\s*=\s*"
                    df_match = re.search(df_pattern, fixed_code)
                    if df_match:
                        # Find the end of that line
                        line_end = fixed_code.find('\n', df_match.end())
                        if line_end == -1:
                            line_end = len(fixed_code)
                        # Get indent
                        line_start = fixed_code.rfind('\n', 0, df_match.start()) + 1
                        indent = len(fixed_code[line_start:df_match.start()]) - len(fixed_code[line_start:df_match.start()].lstrip())
                        indent_str = ' ' * indent
                        fixed_code = fixed_code[:line_end] + f"\n{indent_str}df['Month'] = df['Month'].astype(str)" + fixed_code[line_end:]
                        logger.info("Added df['Month'] = df['Month'].astype(str) after df assignment")
            
            # Also remove any pd.to_datetime calls on Month column (regex fallback)
            if 'pd.to_datetime' in fixed_code and 'Month' in fixed_code:
                # Remove pd.to_datetime(df['Month']) patterns
                fixed_code = re.sub(
                    r"pd\.to_datetime\(df\[['\"]Month['\"]\]\)",
                    "df['Month']",
                    fixed_code
                )
                logger.info("Removed pd.to_datetime calls on Month column")
            
            # CRITICAL: Ensure Plotly treats Month as categorical (not datetime)
            # Add category_orders or xaxis_type='category' if not present
            if 'Month' in fixed_code and ('px.' in fixed_code or 'plotly.express' in fixed_code):
                # Check if category_orders is already present
                if 'category_orders' not in fixed_code:
                    # Find where the figure is assigned (e.g., figure = px.line(...) or fig = px.line(...))
                    # Then add update_layout to set xaxis_type='category' instead of modifying the call
                    fig_pattern = r"(figure\s*=\s*px\.\w+\([^)]*x\s*=\s*['\"]Month['\"][^)]*\)|fig\s*=\s*px\.\w+\([^)]*x\s*=\s*['\"]Month['\"][^)]*\))"
                    fig_match = re.search(fig_pattern, fixed_code, re.MULTILINE | re.DOTALL)
                    
                    if not fig_match:
                        # Try to find any px. call with Month
                        lines = fixed_code.split('\n')
                        for i, line in enumerate(lines):
                            if 'px.' in line and 'Month' in line:
                                # Find the end of this statement
                                start_pos = fixed_code.find(line)
                                # Find matching closing paren
                                paren_count = line.count('(') - line.count(')')
                                current_pos = start_pos + len(line)
                                
                                if paren_count > 0:
                                    while current_pos < len(fixed_code) and paren_count > 0:
                                        char = fixed_code[current_pos]
                                        if char == '(':
                                            paren_count += 1
                                        elif char == ')':
                                            paren_count -= 1
                                        current_pos += 1
                                
                                # Find end of line
                                line_end = fixed_code.find('\n', current_pos)
                                if line_end == -1:
                                    line_end = len(fixed_code)
                                
                                # Calculate indent
                                indent = len(line) - len(line.lstrip())
                                indent_str = ' ' * indent
                                
                                # Add update_layout call after the px. call
                                # Use xaxis_type='category' instead of category_orders (safer)
                                # Try to detect the variable name (figure, fig, etc.)
                                var_name = 'figure'  # default
                                if 'figure =' in line or 'figure=' in line:
                                    var_name = 'figure'
                                elif 'fig =' in line or 'fig=' in line:
                                    var_name = 'fig'
                                else:
                                    # Try to extract variable name from assignment
                                    assign_match = re.search(r'(\w+)\s*=\s*px\.', line)
                                    if assign_match:
                                        var_name = assign_match.group(1)
                                
                                fixed_code = fixed_code[:line_end] + f"\n{indent_str}{var_name}.update_layout(xaxis_type='category')" + fixed_code[line_end:]
                                logger.info(f"Added update_layout with xaxis_type='category' for Plotly express (using {var_name})")
                                break
                    else:
                        # Found figure assignment, add update_layout after it
                        match_end = fig_match.end()
                        line_end = fixed_code.find('\n', match_end)
                        if line_end == -1:
                            line_end = len(fixed_code)
                        
                        # Get indent from the matched line
                        match_start = fig_match.start()
                        line_start = fixed_code.rfind('\n', 0, match_start) + 1
                        indent = len(fixed_code[line_start:match_start]) - len(fixed_code[line_start:match_start].lstrip())
                        indent_str = ' ' * indent
                        
                        # Detect variable name from the match
                        match_text = fig_match.group(1)
                        var_name = 'figure'  # default
                        if 'figure =' in match_text or 'figure=' in match_text:
                            var_name = 'figure'
                        elif 'fig =' in match_text or 'fig=' in match_text:
                            var_name = 'fig'
                        else:
                            var_match = re.search(r'(\w+)\s*=\s*px\.', match_text)
                            if var_match:
                                var_name = var_match.group(1)
                        
                        # Add update_layout
                        fixed_code = fixed_code[:line_end] + f"\n{indent_str}{var_name}.update_layout(xaxis_type='category')" + fixed_code[line_end:]
                        logger.info(f"Added update_layout with xaxis_type='category' for Plotly express (using {var_name})")
            
            # Also ensure xaxis_type='category' for plotly.graph_objects
            if 'Month' in fixed_code and ('go.Figure' in fixed_code or 'plotly.graph_objects' in fixed_code):
                # Check if xaxis_type is already set
                if "xaxis_type='category'" not in fixed_code and 'xaxis_type="category"' not in fixed_code:
                    # Try to add update_layout call
                    if 'fig.update_layout' in fixed_code:
                        # Add xaxis_type to existing update_layout
                        fixed_code = re.sub(
                            r"(fig\.update_layout\([^)]*)\)",
                            r"\1, xaxis_type='category')",
                            fixed_code
                        )
                        logger.info("Added xaxis_type='category' to existing update_layout")
                    elif 'figure =' in fixed_code or 'fig =' in fixed_code:
                        # Add update_layout call after figure creation
                        fig_pattern = r"(figure\s*=\s*[^\n]+|fig\s*=\s*[^\n]+)"
                        fig_match = re.search(fig_pattern, fixed_code)
                        if fig_match:
                            insert_pos = fixed_code.find('\n', fig_match.end())
                            if insert_pos == -1:
                                insert_pos = len(fixed_code)
                            indent = len(fixed_code[:fig_match.start()].split('\n')[-1]) - len(fixed_code[:fig_match.start()].split('\n')[-1].lstrip())
                            indent_str = ' ' * indent
                            fixed_code = fixed_code[:insert_pos] + f"\n{indent_str}figure.update_layout(xaxis_type='category')" + fixed_code[insert_pos:]
                            logger.info("Added update_layout with xaxis_type='category'")
            
            return fixed_code
            
        except AttributeError:
            # Fallback for Python < 3.9: use regex-based fixes
            logger.warning("ast.unparse not available, using regex-based fixes")
            # Apply regex fixes directly
            if 'Month' in code and 'astype(str)' not in code:
                # Add string conversion after pd.read_sql_query
                import re
                pattern = r"(df\s*=\s*pd\.read_sql_query\([^)]+\))"
                match = re.search(pattern, code)
                if match:
                    insert_pos = match.end()
                    lines = code[:insert_pos].split('\n')
                    if lines:
                        last_line = lines[-1]
                        indent = len(last_line) - len(last_line.lstrip())
                        indent_str = ' ' * indent
                        code = code[:insert_pos] + f"\n{indent_str}df['Month'] = df['Month'].astype(str)" + code[insert_pos:]
            return code
        
    except SyntaxError as e:
        logger.error(f"Syntax error in generated code: {e}")
        # Try regex-based fix as fallback
        if 'Month' in code and 'astype(str)' not in code:
            import re
            pattern = r"(df\s*=\s*pd\.read_sql_query\([^)]+\))"
            match = re.search(pattern, code)
            if match:
                insert_pos = match.end()
                lines = code[:insert_pos].split('\n')
                if lines:
                    last_line = lines[-1]
                    indent = len(last_line) - len(last_line.lstrip())
                    indent_str = ' ' * indent
                    code = code[:insert_pos] + f"\n{indent_str}df['Month'] = df['Month'].astype(str)" + code[insert_pos:]
        return code
    except Exception as e:
        logger.error(f"Error in AST transformation: {e}")
        # Try regex-based fix as fallback
        if 'Month' in code and 'astype(str)' not in code:
            import re
            pattern = r"(df\s*=\s*pd\.read_sql_query\([^)]+\))"
            match = re.search(pattern, code)
            if match:
                insert_pos = match.end()
                lines = code[:insert_pos].split('\n')
                if lines:
                    last_line = lines[-1]
                    indent = len(last_line) - len(last_line.lstrip())
                    indent_str = ' ' * indent
                    code = code[:insert_pos] + f"\n{indent_str}df['Month'] = df['Month'].astype(str)" + code[insert_pos:]
        return code


def fix_sql_code(sql: str) -> tuple[str, Optional[str]]:
    """
    Fix SQL code using validators and fixers.
    
    Args:
        sql: SQL query string
        
    Returns:
        Tuple of (fixed_sql, error_message)
    """
    # Validate security first
    is_safe, error = SecurityValidator.validate_sql(sql)
    if not is_safe:
        return sql, error
    
    # Fix reserved keywords
    fixed_sql = SQLKeywordFixer.fix_reserved_keywords(sql)
    
    return fixed_sql, None

