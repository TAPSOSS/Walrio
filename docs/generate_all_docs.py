#!/usr/bin/env python3
"""
Master Documentation Generator
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Runs all documentation generators to build comprehensive Walrio documentation,
including API docs, CLI docs, GUI docs (with MVC architecture), and auto-generated READMEs.
"""

import subprocess
import sys
from pathlib import Path


def run_generator(script_name: str, description: str) -> bool:
    """
    Run a documentation generator script.
    
    Args:
        script_name (str): Name of the generator script
        description (str): Description for logging
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n🚀 {description}...")
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            # Show key output lines
            lines = result.stdout.strip().split('\n')
            for line in lines[-3:]:  # Show last 3 lines
                if line.strip():
                    print(f"   {line}")
            return True
        else:
            print(f"❌ {description} failed with exit code {result.returncode}")
            if result.stderr:
                print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏱️  {description} timed out")
        return False
    except Exception as e:
        print(f"💥 {description} crashed: {e}")
        return False


def main():
    """
    Run all documentation generators.
    """
    print("📚 Walrio Documentation Generator")
    print("=" * 50)
    
    generators = [
        ("generate_api_docs.py", "API Documentation Generation"),
        ("generate_cli_docs.py", "CLI Documentation Generation"),  
        ("generate_gui_docs.py", "GUI Documentation Generation"),
    ]
    
    results = []
    total_generators = len(generators)
    
    for script, description in generators:
        success = run_generator(script, description)
        results.append((description, success))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Documentation Generation Summary")
    print("=" * 50)
    
    successful = sum(1 for _, success in results if success)
    
    for description, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {description}")
    
    print(f"\n📊 Results: {successful}/{total_generators} generators completed successfully")
    
    if successful == total_generators:
        print("🎉 All documentation generated successfully!")
        print("\n📖 Documentation files generated:")
        print("   • docs/source/api/index.rst - API documentation")
        print("   • docs/source/cli_usage.rst - CLI documentation")  
        print("   • docs/source/gui_usage.rst - GUI documentation")
        
        print("\n🏗️  To build HTML documentation:")
        print("   cd docs && make html")
        
    else:
        failed_count = total_generators - successful
        print(f"⚠️  {failed_count} generator(s) failed. Check output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()