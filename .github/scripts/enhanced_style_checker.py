#!/usr/bin/env python3
"""
Enhanced style checker for Walrio project
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Provides detailed feedback on BSD header and docstring requirements
"""

import ast
import sys
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Tuple

class StyleIssue:
    """
    Represents a style violation found during code analysis.
    
    Stores information about style issues including severity, category, message, and line number.
    """
    def __init__(self, severity: str, category: str, message: str, line: int = None):
        """
        Initialize a new style issue.
        
        Args:
            severity (str): Severity level (ERROR, WARNING, INFO)
            category (str): Issue category (HEADER, DOCSTRING, SYNTAX)
            message (str): Descriptive message about the issue
            line (int, optional): Line number where the issue occurs
        """
        self.severity = severity  # ERROR, WARNING, INFO
        self.category = category  # HEADER, DOCSTRING, SYNTAX
        self.message = message
        self.line = line

def check_bsd_header(file_content: str, filename: str) -> List[StyleIssue]:
    """
    Check if file has required BSD-3-Clause header with detailed feedback.
    
    Args:
        file_content (str): The content of the Python file to check
        filename (str): Name of the file being checked for error reporting
        
    Returns:
        List[StyleIssue]: List of style issues found in the BSD header
    """
    issues = []
    required_elements = {
        "Copyright (c) 2025 TAPS OSS": "copyright notice",
        "Project: https://github.com/TAPSOSS/Walrio": "project URL",
        "Licensed under the BSD-3-Clause License": "license declaration"
    }
    
    # Check first 20 lines for header
    lines = file_content.split('\n')[:20]
    header_text = '\n'.join(lines)
    
    # Check if file starts with proper docstring
    if not file_content.strip().startswith('"""') and not file_content.strip().startswith("'''"):
        if not file_content.strip().startswith('#!'):  # Allow shebang
            issues.append(StyleIssue("ERROR", "HEADER", 
                "File must start with a docstring containing the BSD header"))
    
    missing_elements = []
    for element, description in required_elements.items():
        if element not in header_text:
            missing_elements.append(f"• {description}: '{element}'")
    
    if missing_elements:
        issues.append(StyleIssue("ERROR", "HEADER", 
            f"Missing required BSD header elements:\n" + "\n".join(missing_elements)))
    
    return issues

def analyze_function_signature(node: ast.FunctionDef) -> Dict:
    """
    Analyze function signature to determine docstring requirements.
    
    Args:
        node (ast.FunctionDef): AST node representing the function definition
        
    Returns:
        Dict: Dictionary containing signature analysis results with keys:
            - params: List of parameter names (excluding self/cls)
            - has_varargs: Boolean indicating presence of *args
            - has_kwargs: Boolean indicating presence of **kwargs
            - has_return: Boolean indicating meaningful return statements
            - param_count: Number of parameters
    """
    # Get parameters (excluding 'self' and 'cls')
    params = []
    for arg in node.args.args:
        if arg.arg not in ['self', 'cls']:
            params.append(arg.arg)
    
    # Check for *args and **kwargs
    has_varargs = node.args.vararg is not None
    has_kwargs = node.args.kwarg is not None
    
    # Check if function has return statements with values
    has_meaningful_return = False
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value is not None:
            # Skip return None
            if not (isinstance(child.value, ast.Constant) and child.value.value is None):
                has_meaningful_return = True
                break
        elif isinstance(child, ast.Yield) or isinstance(child, ast.YieldFrom):
            has_meaningful_return = True
            break
    
    return {
        'params': params,
        'has_varargs': has_varargs,
        'has_kwargs': has_kwargs,
        'has_return': has_meaningful_return,
        'param_count': len(params)
    }

def check_docstring_content(docstring: str, func_info: Dict, func_name: str) -> List[str]:
    """
    Check if docstring has proper structure and content.
    
    Args:
        docstring (str): The docstring content to analyze
        func_info (Dict): Function signature information from analyze_function_signature
        func_name (str): Name of the function being checked
        
    Returns:
        List[str]: List of issues found in the docstring content
    """
    issues = []
    
    # Check for basic description
    lines = [line.strip() for line in docstring.split('\n') if line.strip()]
    if not lines:
        issues.append("Empty docstring - needs a description")
        return issues
    
    # Check for parameters documentation
    needs_args = func_info['param_count'] > 0 or func_info['has_varargs'] or func_info['has_kwargs']
    has_args_section = any('Args:' in line or 'Arguments:' in line or 'Parameters:' in line 
                         for line in lines)
    
    if needs_args and not has_args_section:
        param_list = func_info['params']
        if func_info['has_varargs']:
            param_list.append('*args')
        if func_info['has_kwargs']:
            param_list.append('**kwargs')
        issues.append(f"Missing 'Args:' section for parameters: {', '.join(param_list)}")
    
    # Check for return documentation
    needs_returns = func_info['has_return']
    has_returns_section = any('Returns:' in line or 'Return:' in line or 'Yields:' in line 
                            for line in lines)
    
    if needs_returns and not has_returns_section:
        issues.append("Missing 'Returns:' section (function has return statements)")
    
    # Check for proper formatting
    if has_args_section:
        args_found = False
        for line in lines:
            if 'Args:' in line or 'Arguments:' in line or 'Parameters:' in line:
                args_found = True
                continue
            if args_found and line and not line.startswith(' '):
                break
            if args_found and ':' in line and '(' in line and ')' in line:
                # Good parameter format found
                break
        else:
            if args_found:
                issues.append("Args section found but parameters not properly formatted (need 'param (type): description')")
    
    return issues

def check_docstrings(file_content: str, filename: str) -> List[StyleIssue]:
    """
    Check docstrings with detailed analysis and feedback.
    
    Args:
        file_content (str): The content of the Python file to analyze
        filename (str): Name of the file being checked for error reporting
        
    Returns:
        List[StyleIssue]: List of docstring-related style issues found
    """
    issues = []
    
    try:
        tree = ast.parse(file_content)
    except SyntaxError as e:
        issues.append(StyleIssue("ERROR", "SYNTAX", f"Syntax error prevents analysis: {e}", e.lineno))
        return issues
    
    def check_node_docstring(node, node_type: str):
        """
        Check individual function or class docstring.
        
        Args:
            node: AST node representing a function or class definition
            node_type (str): Type of node being checked ("Function" or "Class")
            
        Returns:
            List[StyleIssue]: List of docstring issues found for this node
        """
        node_issues = []
        
        # Check if docstring exists
        docstring = ast.get_docstring(node)
        if not docstring:
            node_issues.append(StyleIssue("ERROR", "DOCSTRING",
                f"{node_type} '{node.name}' missing docstring", node.lineno))
            return node_issues
        
        # For functions, do detailed analysis
        if isinstance(node, ast.FunctionDef):
            func_info = analyze_function_signature(node)
            docstring_issues = check_docstring_content(docstring, func_info, node.name)
            
            for issue in docstring_issues:
                node_issues.append(StyleIssue("ERROR", "DOCSTRING",
                    f"Function '{node.name}': {issue}", node.lineno))
        
        # For classes, basic check
        elif isinstance(node, ast.ClassDef):
            if len(docstring.strip()) < 10:
                node_issues.append(StyleIssue("WARNING", "DOCSTRING",
                    f"Class '{node.name}': docstring too brief (needs class purpose)", node.lineno))
        
        return node_issues
    
    # Check all functions and classes
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            issues.extend(check_node_docstring(node, "Function"))
    
    return issues

def check_emoji_usage(file_content: str, filename: str) -> List[StyleIssue]:
    """
    Check for emoji usage in modules directory files.
    
    Emojis are not allowed in the modules directory as they can cause display
    issues on different terminals and reduce accessibility.
    
    Args:
        file_content (str): The content of the Python file to check
        filename (str): Name of the file being checked for error reporting
        
    Returns:
        List[StyleIssue]: List of emoji-related style issues found
    """
    issues = []
    
    # Only check files in the modules directory (must start with "modules/" or be exactly "modules/...")
    # This ensures we don't check files outside the modules folder even if they contain "modules" in their path
    import os
    normalized_path = filename.replace('\\', '/')  # Handle Windows paths
    if not (normalized_path.startswith('modules/') or 
            normalized_path.startswith('./modules/') or 
            normalized_path.startswith('../modules/') or
            os.path.basename(os.path.dirname(normalized_path)) == 'modules'):
        return issues
    
    lines = file_content.split('\n')
    
    for line_num, line in enumerate(lines, 1):
        # Check each character in the line for emoji
        for char_pos, char in enumerate(line):
            # Check if character is an emoji using Unicode categories
            if unicodedata.category(char) in ['So', 'Sm']:  # Symbol, other / Symbol, math
                # Additional check for common emoji ranges
                code_point = ord(char)
                if (0x1F600 <= code_point <= 0x1F64F or  # Emoticons
                    0x1F300 <= code_point <= 0x1F5FF or  # Misc Symbols and Pictographs
                    0x1F680 <= code_point <= 0x1F6FF or  # Transport and Map
                    0x1F1E0 <= code_point <= 0x1F1FF or  # Regional indicators
                    0x2600 <= code_point <= 0x26FF or    # Misc symbols
                    0x2700 <= code_point <= 0x27BF or    # Dingbats
                    0xFE00 <= code_point <= 0xFE0F or    # Variation selectors
                    0x1F900 <= code_point <= 0x1F9FF or  # Supplemental Symbols and Pictographs
                    0x1FA70 <= code_point <= 0x1FAFF):   # Symbols and Pictographs Extended-A
                    
                    # Get a snippet of the line around the emoji for context
                    start_pos = max(0, char_pos - 10)
                    end_pos = min(len(line), char_pos + 10)
                    context = line[start_pos:end_pos]
                    if start_pos > 0:
                        context = "..." + context
                    if end_pos < len(line):
                        context = context + "..."
                    
                    issues.append(StyleIssue("ERROR", "EMOJI",
                        f"Emoji '{char}' found in modules file. Context: '{context}'", line_num))
            
            # Also check for specific common emoji sequences that might not be caught above
            elif char in ['✅', '❌', '⚠️', '🚫', '⏭️', '▶', '🎉', '✓', '✗', '🔧', '🔍', '📁', '📋', '📖', '🛠️', '🚀', '🎊']:
                # Get context around the emoji
                start_pos = max(0, char_pos - 10)
                end_pos = min(len(line), char_pos + 10)
                context = line[start_pos:end_pos]
                if start_pos > 0:
                    context = "..." + context
                if end_pos < len(line):
                    context = context + "..."
                
                issues.append(StyleIssue("ERROR", "EMOJI",
                    f"Emoji '{char}' found in modules file. Context: '{context}'", line_num))
    
    return issues

def format_issues_summary(issues: List[StyleIssue], filename: str) -> str:
    """
    Format issues into a readable summary.
    
    Args:
        issues (List[StyleIssue]): List of style issues to format
        filename (str): Name of the file being reported on
        
    Returns:
        str: Formatted summary string with issue details
    """
    if not issues:
        return f"✅ {filename}: All style checks passed"
    
    # Group by category
    by_category = {}
    for issue in issues:
        if issue.category not in by_category:
            by_category[issue.category] = []
        by_category[issue.category].append(issue)
    
    output = [f"\n❌ {filename}: Found {len(issues)} styling issue(s)"]
    
    for category, cat_issues in by_category.items():
        output.append(f"\n  📋 {category} Issues ({len(cat_issues)}):")
        for issue in cat_issues:
            line_info = f" (line {issue.line})" if issue.line else ""
            output.append(f"     • {issue.message}{line_info}")
    
    return "\n".join(output)

def generate_fix_suggestions(issues: List[StyleIssue]) -> str:
    """
    Generate specific fix suggestions based on issues found.
    
    Args:
        issues (List[StyleIssue]): List of style issues to generate suggestions for
        
    Returns:
        str: Formatted string containing fix suggestions
    """
    suggestions = []
    
    header_issues = [i for i in issues if i.category == "HEADER"]
    docstring_issues = [i for i in issues if i.category == "DOCSTRING"]
    emoji_issues = [i for i in issues if i.category == "EMOJI"]
    
    if header_issues:
        suggestions.append("""
🔧 BSD Header Fix:
   Add this header at the top of your Python file:
   
   '''
   Short description of the module/script
   Copyright (c) 2025 TAPS OSS
   Project: https://github.com/TAPSOSS/Walrio
   Licensed under the BSD-3-Clause License (see LICENSE file for details)
   
   Longer description of what this module does...
   '''
        """)
    
    if docstring_issues:
        missing_docstrings = [i for i in docstring_issues if "missing docstring" in i.message]
        param_issues = [i for i in docstring_issues if "Args:" in i.message]
        return_issues = [i for i in docstring_issues if "Returns:" in i.message]
        
        if missing_docstrings:
            suggestions.append("""
🔧 Missing Docstring Fix:
   Add docstrings to functions/classes:
   
   def my_function(param1, param2):
       '''
       Brief description of what the function does.
       
       Args:
           param1 (str): Description of param1
           param2 (int): Description of param2
           
       Returns:
           bool: Description of return value
       '''
            """)
        
        if param_issues:
            suggestions.append("""
🔧 Parameter Documentation Fix:
   Add Args section to your docstrings:
   
   Args:
       parameter_name (type): Description of what this parameter does
       another_param (str): Another parameter description
            """)
        
        if return_issues:
            suggestions.append("""
🔧 Return Documentation Fix:
   Add Returns section to your docstrings:
   
   Returns:
       return_type: Description of what is returned
            """)
    
    if emoji_issues:
        suggestions.append("""
🔧 Emoji Usage Fix:
   Remove emojis from modules directory files. Replace with text equivalents:
   
   Instead of: print("✅ Success!")
   Use:        print("SUCCESS: Operation completed!")
   
   Instead of: logger.error("❌ Failed!")
   Use:        logger.error("ERROR: Operation failed!")
   
   Emojis can cause display issues and reduce accessibility.
            """)
    
    return "\n".join(suggestions) if suggestions else ""

def main():
    """
    Main function to run the enhanced style checker.
    
    Processes command line arguments and runs style checks on specified Python files.
    Exits with code 1 if any style issues are found, 0 if all files pass.
    """
    if len(sys.argv) < 2:
        print("Usage: python enhanced_style_checker.py <file1.py> [file2.py ...]")
        sys.exit(1)
    
    all_issues = []
    total_files_checked = 0
    files_with_issues = 0
    
    print("🔍 Enhanced Walrio Style Checker")
    print("=" * 50)
    
    for filename in sys.argv[1:]:
        total_files_checked += 1
        print(f"\n📁 Analyzing {filename}...")
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ {filename}: Could not read file - {e}")
            all_issues.append(StyleIssue("ERROR", "FILE", f"Could not read {filename}: {e}"))
            files_with_issues += 1
            continue
        
        # Collect all issues for this file
        file_issues = []
        file_issues.extend(check_bsd_header(content, filename))
        file_issues.extend(check_docstrings(content, filename))
        file_issues.extend(check_emoji_usage(content, filename))
        
        # Print summary for this file
        print(format_issues_summary(file_issues, filename))
        
        if file_issues:
            files_with_issues += 1
            all_issues.extend(file_issues)
    
    # Final summary
    print("\n" + "=" * 50)
    print(f"📊 Style Check Summary")
    print(f"   Files checked: {total_files_checked}")
    print(f"   Files with issues: {files_with_issues}")
    print(f"   Total issues: {len(all_issues)}")
    
    if all_issues:
        print(f"\n❌ Style check failed!")
        
        # List specific functions with docstring issues
        docstring_issues = [issue for issue in all_issues if issue.category == "DOCSTRING"]
        if docstring_issues:
            print(f"\n📋 Functions/Classes requiring docstring fixes:")
            
            # Group by file
            by_file = {}
            for issue in docstring_issues:
                # Extract function name from message
                if "Function '" in issue.message and "'" in issue.message:
                    func_name = issue.message.split("Function '")[1].split("'")[0]
                    file_key = None
                    # Find which file this issue belongs to
                    for filename in sys.argv[1:]:
                        if filename not in by_file:
                            by_file[filename] = []
                        # Check if this issue is from this file by checking line numbers
                        # For now, we'll use a simpler approach
                    
                    # Simplified: just list all function issues
                    if "missing docstring" in issue.message:
                        print(f"   ❌ {func_name}() - missing docstring (line {issue.line})")
                    elif "Missing 'Args:'" in issue.message:
                        print(f"   ⚠️  {func_name}() - missing Args section (line {issue.line})")
                    elif "Missing 'Returns:'" in issue.message:
                        print(f"   ⚠️  {func_name}() - missing Returns section (line {issue.line})")
                    else:
                        print(f"   ⚠️  {func_name}() - {issue.message.split(': ', 1)[1] if ': ' in issue.message else issue.message} (line {issue.line})")
                elif "Class '" in issue.message and "'" in issue.message:
                    class_name = issue.message.split("Class '")[1].split("'")[0]
                    print(f"   ⚠️  {class_name} (class) - {issue.message.split(': ', 1)[1] if ': ' in issue.message else issue.message} (line {issue.line})")
        
        # Show fix suggestions
        suggestions = generate_fix_suggestions(all_issues)
        if suggestions:
            print("\n🛠️  Fix Suggestions:")
            print(suggestions)
        
        print("\n📖 Complete style guide: https://github.com/TAPSOSS/Walrio/blob/main/CONTRIBUTING.md#styling-requirements")
        sys.exit(1)
    else:
        print(f"\n🎉 All files passed style requirements!")
        print("📖 Style guide: https://github.com/TAPSOSS/Walrio/blob/main/CONTRIBUTING.md#styling-requirements")

if __name__ == "__main__":
    main()
