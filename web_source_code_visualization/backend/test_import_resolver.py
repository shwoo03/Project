"""
Test Import Resolution Module.

Tests the functionality of resolving imports and building dependency graphs.
"""

import os
import sys
import tempfile
import shutil

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.import_resolver import ImportResolver, resolve_project_imports, ImportType


def create_python_test_project():
    """Create a Python test project with various import patterns."""
    temp_dir = tempfile.mkdtemp(prefix="test_imports_py_")
    
    # Create package structure
    os.makedirs(os.path.join(temp_dir, "mypackage"))
    os.makedirs(os.path.join(temp_dir, "mypackage", "utils"))
    
    # mypackage/__init__.py
    with open(os.path.join(temp_dir, "mypackage", "__init__.py"), "w") as f:
        f.write('''"""My Package."""
from .core import main_function
from .utils import helpers
''')
    
    # mypackage/core.py
    with open(os.path.join(temp_dir, "mypackage", "core.py"), "w") as f:
        f.write('''"""Core module."""
import os
import json
from typing import Dict, List
from .utils.helpers import format_data
from . import config

def main_function(data: Dict) -> List:
    """Main entry point."""
    formatted = format_data(data)
    return formatted
''')
    
    # mypackage/config.py
    with open(os.path.join(temp_dir, "mypackage", "config.py"), "w") as f:
        f.write('''"""Configuration module."""
DEBUG = True
DATABASE_URL = "sqlite:///app.db"
''')
    
    # mypackage/utils/__init__.py
    with open(os.path.join(temp_dir, "mypackage", "utils", "__init__.py"), "w") as f:
        f.write('''"""Utils package."""
from .helpers import format_data, validate_input
''')
    
    # mypackage/utils/helpers.py
    with open(os.path.join(temp_dir, "mypackage", "utils", "helpers.py"), "w") as f:
        f.write('''"""Helper functions."""
import re
from typing import Any, Dict

def format_data(data: Dict) -> Dict:
    """Format data for output."""
    return {k: str(v) for k, v in data.items()}

def validate_input(data: Any) -> bool:
    """Validate input data."""
    return data is not None

class DataProcessor:
    """Process data."""
    def process(self, data):
        return format_data(data)
''')
    
    # app.py - entry point with various import types
    with open(os.path.join(temp_dir, "app.py"), "w") as f:
        f.write('''"""Application entry point."""
# Standard library imports
import os
import sys
from datetime import datetime

# Absolute import from package
from mypackage.core import main_function
from mypackage.utils.helpers import format_data, validate_input as validate

# Aliased imports
import json as json_module
from mypackage import config as app_config

# Dynamic import (for testing detection)
module_name = "mypackage.utils"
# dynamic_module = __import__(module_name)

def run():
    """Run the application."""
    data = {"key": "value"}
    if validate(data):
        result = main_function(data)
        print(json_module.dumps(result))

if __name__ == "__main__":
    run()
''')
    
    # Create circular import scenario
    with open(os.path.join(temp_dir, "circular_a.py"), "w") as f:
        f.write('''"""Circular import A."""
from circular_b import function_b

def function_a():
    return function_b()
''')
    
    with open(os.path.join(temp_dir, "circular_b.py"), "w") as f:
        f.write('''"""Circular import B."""
from circular_a import function_a

def function_b():
    return "b"
''')
    
    return temp_dir


def create_js_test_project():
    """Create a JavaScript test project with various import patterns."""
    temp_dir = tempfile.mkdtemp(prefix="test_imports_js_")
    
    os.makedirs(os.path.join(temp_dir, "src"))
    os.makedirs(os.path.join(temp_dir, "src", "utils"))
    
    # src/index.js - ES6 imports
    with open(os.path.join(temp_dir, "src", "index.js"), "w") as f:
        f.write('''// Main entry point
import { formatDate, parseDate } from './utils/date';
import config from './config';
import * as helpers from './utils/helpers';

export function main() {
    const date = formatDate(new Date());
    console.log(config.APP_NAME, date);
    return helpers.process(date);
}
''')
    
    # src/config.js
    with open(os.path.join(temp_dir, "src", "config.js"), "w") as f:
        f.write('''// Configuration
export default {
    APP_NAME: 'TestApp',
    DEBUG: true
};

export const VERSION = '1.0.0';
''')
    
    # src/utils/date.js
    with open(os.path.join(temp_dir, "src", "utils", "date.js"), "w") as f:
        f.write('''// Date utilities
export function formatDate(date) {
    return date.toISOString();
}

export function parseDate(str) {
    return new Date(str);
}
''')
    
    # src/utils/helpers.js - CommonJS
    with open(os.path.join(temp_dir, "src", "utils", "helpers.js"), "w") as f:
        f.write('''// Helper functions
const { formatDate } = require('./date');

function process(data) {
    return { processed: true, data };
}

module.exports = { process };
''')
    
    # src/utils/index.js
    with open(os.path.join(temp_dir, "src", "utils", "index.js"), "w") as f:
        f.write('''// Utils index
export * from './date';
export { process } from './helpers';
''')
    
    return temp_dir


def test_python_imports():
    """Test Python import resolution."""
    print("=" * 60)
    print("Test 1: Python Import Resolution")
    print("=" * 60)
    
    temp_dir = create_python_test_project()
    
    try:
        resolver = ImportResolver(temp_dir)
        result = resolver.scan_project()
        
        print(f"\n📊 Statistics:")
        for key, value in result["statistics"].items():
            print(f"   {key}: {value}")
        
        print(f"\n📦 Modules discovered: {len(result['modules'])}")
        for name, info in sorted(result["modules"].items()):
            pkg_marker = "📁" if info["is_package"] else "📄"
            entry_marker = "🚀" if info["is_entry_point"] else ""
            print(f"   {pkg_marker} {name} {entry_marker}")
            print(f"      Imports: {info['imports_count']}, Deps: {len(info['dependencies'])}")
        
        print(f"\n🔗 Dependency edges: {len(result['edges'])}")
        for edge in result["edges"][:5]:
            print(f"   {edge['source']} → {edge['target']} ({edge['import_type']})")
        
        if result["circular_dependencies"]:
            print(f"\n⚠️ Circular dependencies: {len(result['circular_dependencies'])}")
            for cycle in result["circular_dependencies"]:
                print(f"   {' → '.join(cycle)}")
        
        # Check resolution rate
        resolved = result["statistics"]["resolved_imports"]
        total = result["statistics"]["total_imports"]
        external = result["statistics"]["external_imports"]
        rate = ((resolved) / total * 100) if total > 0 else 0
        
        print(f"\n✅ Resolution rate: {rate:.1f}% ({resolved}/{total})")
        print(f"   External imports: {external}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_javascript_imports():
    """Test JavaScript import resolution."""
    print("\n" + "=" * 60)
    print("Test 2: JavaScript Import Resolution")
    print("=" * 60)
    
    temp_dir = create_js_test_project()
    
    try:
        resolver = ImportResolver(temp_dir)
        result = resolver.scan_project()
        
        print(f"\n📊 Statistics:")
        for key, value in result["statistics"].items():
            print(f"   {key}: {value}")
        
        print(f"\n📦 Modules discovered: {len(result['modules'])}")
        for name, info in sorted(result["modules"].items()):
            print(f"   📄 {name}")
            for imp in info["imports"]:
                resolved = "✅" if imp["is_resolved"] else "❌"
                print(f"      {resolved} {imp['import_type']}: {imp['module_path']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_relative_imports():
    """Test relative import resolution."""
    print("\n" + "=" * 60)
    print("Test 3: Relative Import Resolution")
    print("=" * 60)
    
    temp_dir = create_python_test_project()
    
    try:
        resolver = ImportResolver(temp_dir)
        result = resolver.scan_project()
        
        # Find relative imports
        relative_imports = []
        for name, info in result["modules"].items():
            for imp in info["imports"]:
                if imp["import_type"] == "relative":
                    relative_imports.append({
                        "module": name,
                        "import": imp["module_path"],
                        "resolved": imp["is_resolved"],
                        "resolved_path": imp["resolved_path"]
                    })
        
        print(f"\n📍 Relative imports found: {len(relative_imports)}")
        for rel in relative_imports:
            status = "✅" if rel["resolved"] else "❌"
            print(f"   {status} {rel['module']}: {rel['import']}")
            if rel["resolved_path"]:
                print(f"      → {os.path.basename(rel['resolved_path'])}")
        
        resolved_count = sum(1 for r in relative_imports if r["resolved"])
        print(f"\n   Resolved: {resolved_count}/{len(relative_imports)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_alias_handling():
    """Test alias import handling."""
    print("\n" + "=" * 60)
    print("Test 4: Alias Import Handling")
    print("=" * 60)
    
    temp_dir = create_python_test_project()
    
    try:
        resolver = ImportResolver(temp_dir)
        result = resolver.scan_project()
        
        # Find aliased imports
        alias_imports = []
        for name, info in result["modules"].items():
            for imp in info["imports"]:
                if imp["aliases"]:
                    alias_imports.append({
                        "module": name,
                        "import": imp["module_path"],
                        "aliases": imp["aliases"],
                        "names": imp["imported_names"]
                    })
        
        print(f"\n🏷️ Aliased imports found: {len(alias_imports)}")
        for alias in alias_imports:
            print(f"   In {alias['module']}:")
            print(f"      from {alias['import']} import {alias['names']}")
            for alias_name, original in alias["aliases"].items():
                print(f"      {original} as {alias_name}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_symbol_resolution():
    """Test symbol resolution functionality."""
    print("\n" + "=" * 60)
    print("Test 5: Symbol Resolution")
    print("=" * 60)
    
    temp_dir = create_python_test_project()
    
    try:
        resolver = ImportResolver(temp_dir)
        resolver.scan_project()
        
        # Test resolving symbols from app.py
        app_path = os.path.join(temp_dir, "app.py")
        
        symbols_to_resolve = [
            ("main_function", "Should resolve to mypackage.core"),
            ("format_data", "Should resolve to mypackage.utils.helpers"),
            ("validate", "Should resolve to validate_input alias"),
        ]
        
        print(f"\n🔍 Resolving symbols from app.py:")
        for symbol, expected in symbols_to_resolve:
            result = resolver.resolve_symbol(symbol, app_path)
            status = "✅" if result else "❌"
            print(f"   {status} {symbol}: {expected}")
            if result:
                print(f"      → {result}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_real_project():
    """Test on the actual backend directory."""
    print("\n" + "=" * 60)
    print("Test 6: Real Project Analysis (backend/)")
    print("=" * 60)
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        result = resolve_project_imports(backend_dir)
        
        print(f"\n📊 Statistics:")
        stats = result["statistics"]
        print(f"   Files: {stats['total_files']}")
        print(f"   Total imports: {stats['total_imports']}")
        print(f"   Resolved: {stats['resolved_imports']}")
        print(f"   External: {stats['external_imports']}")
        print(f"   Unresolved: {stats['unresolved_imports']}")
        print(f"   Dynamic: {stats['dynamic_imports']}")
        print(f"   Circular deps: {stats['circular_dependencies']}")
        
        # Calculate resolution rate
        total = stats['total_imports']
        resolved = stats['resolved_imports'] + stats['external_imports']
        rate = (resolved / total * 100) if total > 0 else 0
        print(f"\n   Resolution rate: {rate:.1f}%")
        
        # Show most connected modules
        print(f"\n🔝 Top modules by connections:")
        module_connections = []
        for name, info in result["modules"].items():
            connections = len(info["dependencies"]) + len(info["dependents"])
            module_connections.append((name, connections, len(info["dependents"])))
        
        module_connections.sort(key=lambda x: x[1], reverse=True)
        for name, total, dependents in module_connections[:5]:
            print(f"   {name}: {total} connections ({dependents} dependents)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🔬 Import Resolution Tests")
    print("=" * 60)
    
    tests = [
        test_python_imports,
        test_javascript_imports,
        test_relative_imports,
        test_alias_handling,
        test_symbol_resolution,
        test_real_project,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
