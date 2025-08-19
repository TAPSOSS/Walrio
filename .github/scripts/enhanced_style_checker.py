#!/usr/bin/env python3
"""
Enhanced style checker for Walrio project
Provides detailed feedback on BSD header and docstring requirements
"""

import ast
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

class StyleIssue:
    def __init__(self, severity: str, category: str, message: str, line: int = None):
        self.severity = severity  # ERROR, WARNING, INFO
        self.category = category  # HEADER, DOCSTRING, SYNTAX
        self.message = message
        self.line = line

def check_bsd_header(file_content: str, filename: str) -> List[StyleIssue]:
    """Check if file has required BSD-3-Clause header with detailed feedback."""
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
    """Analyze function signature to determine docstring requirements."""
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
    """Check if docstring has proper structure and content."""
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
    """Check docstrings with detailed analysis and feedback."""
    issues = []
    
    try:
        tree = ast.parse(file_content)
    except SyntaxError as e:
        issues.append(StyleIssue("ERROR", "SYNTAX", f"Syntax error prevents analysis: {e}", e.lineno))
        return issues
    
    def check_node_docstring(node, node_type: str):
        """Check individual function or class docstring."""
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
        elif isinstance(node, ast.ClassDef):
            issues.extend(check_node_docstring(node, "Class"))
    
    return issues

def format_issues_summary(issues: List[StyleIssue], filename: str) -> str:
    """Format issues into a readable summary."""
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
    """Generate specific fix suggestions based on issues found."""
    suggestions = []
    
    header_issues = [i for i in issues if i.category == "HEADER"]
    docstring_issues = [i for i in issues if i.category == "DOCSTRING"]
    
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
    
    return "\n".join(suggestions) if suggestions else ""

def main():
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
