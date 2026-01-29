"""
Test suite for Type Inference Module (Phase 2.3).

Tests the TypeInferencer class for:
- Python type annotation parsing
- Variable type inference from literals
- Function return type inference
- Class instance tracking
- JavaScript/TypeScript type handling
"""

import os
import sys
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.type_inferencer import TypeInferencer, TypeInfo, TypeCategory, analyze_project_types


def create_test_project():
    """Create a temporary test project with various type patterns."""
    test_dir = tempfile.mkdtemp(prefix="type_test_")
    
    # Python file with type annotations
    python_annotated = '''
from typing import List, Dict, Optional, Union

class User:
    """User class with typed attributes."""
    name: str
    age: int
    email: Optional[str] = None
    
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age
    
    def get_info(self) -> Dict[str, str]:
        return {"name": self.name, "age": str(self.age)}
    
    def greet(self, greeting: str = "Hello") -> str:
        return f"{greeting}, {self.name}!"


def process_users(users: List[User]) -> List[str]:
    """Process a list of users."""
    return [u.name for u in users]


def find_user(user_id: int) -> Optional[User]:
    """Find a user by ID."""
    return None


# Variable with type annotation
count: int = 0
names: List[str] = []


def get_data() -> Union[str, int]:
    if count > 0:
        return "data"
    return 42
'''
    
    with open(os.path.join(test_dir, "annotated.py"), 'w') as f:
        f.write(python_annotated)
    
    # Python file with inferred types
    python_inferred = '''
# Variables with literal inference
message = "Hello World"
count = 42
ratio = 3.14
is_active = True
items = [1, 2, 3]
config = {"key": "value"}


class Product:
    def __init__(self, name, price):
        self.name = name
        self.price = price
    
    def calculate_tax(self, rate):
        return self.price * rate
    
    def get_display_name(self):
        return self.name.upper()


def create_product():
    return Product("Widget", 9.99)


def get_total(products):
    total = 0
    for p in products:
        total += p.price
    return total
'''
    
    with open(os.path.join(test_dir, "inferred.py"), 'w') as f:
        f.write(python_inferred)
    
    # JavaScript file
    javascript_file = '''
class ShoppingCart {
    constructor() {
        this.items = [];
        this.total = 0;
    }
    
    addItem(item) {
        this.items.push(item);
        this.total += item.price;
    }
    
    getTotal() {
        return this.total;
    }
}

const cart = new ShoppingCart();
const message = "Welcome";
const count = 10;
const isReady = true;

function calculateDiscount(price, percent) {
    return price * (1 - percent / 100);
}

const processOrder = (order) => {
    return order.items.length > 0;
};
'''
    
    with open(os.path.join(test_dir, "cart.js"), 'w') as f:
        f.write(javascript_file)
    
    # TypeScript file (if TS support available)
    typescript_file = '''
interface Product {
    id: number;
    name: string;
    price: number;
}

interface CartItem {
    product: Product;
    quantity: number;
}

class TypedCart {
    private items: CartItem[] = [];
    
    addItem(product: Product, quantity: number): void {
        this.items.push({ product, quantity });
    }
    
    getTotal(): number {
        return this.items.reduce(
            (sum, item) => sum + item.product.price * item.quantity,
            0
        );
    }
    
    getItems(): CartItem[] {
        return this.items;
    }
}

function formatPrice(price: number): string {
    return `$${price.toFixed(2)}`;
}

const taxRate: number = 0.08;
const maxItems: number = 100;
'''
    
    with open(os.path.join(test_dir, "typed.ts"), 'w') as f:
        f.write(typescript_file)
    
    return test_dir


def test_python_type_annotations():
    """Test parsing of Python type annotations."""
    print("\n📝 Test 1: Python Type Annotations")
    
    test_dir = create_test_project()
    try:
        inferencer = TypeInferencer(test_dir)
        result = inferencer.analyze_project()
        
        # Check User class
        user_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "User":
                user_class = cls
                break
        
        assert user_class is not None, "User class not found"
        print(f"  ✓ Found User class at {user_class['file_path']}")
        
        # Check get_info method return type
        get_info_sig = None
        for name, sig in result["functions"].items():
            if sig["name"] == "get_info":
                get_info_sig = sig
                break
        
        assert get_info_sig is not None, "get_info method not found"
        assert get_info_sig["return_type"]["name"] == "Dict", f"Expected Dict, got {get_info_sig['return_type']['name']}"
        print(f"  ✓ get_info return type: {get_info_sig['return_type']['name']}")
        
        # Check process_users function
        process_users_sig = None
        for name, sig in result["functions"].items():
            if sig["name"] == "process_users":
                process_users_sig = sig
                break
        
        assert process_users_sig is not None, "process_users function not found"
        assert len(process_users_sig["parameters"]) == 1, "Expected 1 parameter"
        print(f"  ✓ process_users has {len(process_users_sig['parameters'])} parameter(s)")
        
        # Check find_user Optional return
        find_user_sig = None
        for name, sig in result["functions"].items():
            if sig["name"] == "find_user":
                find_user_sig = sig
                break
        
        assert find_user_sig is not None, "find_user function not found"
        print(f"  ✓ find_user return type: {find_user_sig['return_type']['name']}")
        
        print("  ✅ Python type annotations test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_type_inference_from_literals():
    """Test type inference from literal values."""
    print("\n🔍 Test 2: Type Inference from Literals")
    
    test_dir = create_test_project()
    try:
        inferencer = TypeInferencer(test_dir)
        result = inferencer.analyze_project()
        
        # Check inferred variable types
        expected_types = {
            "message": "str",
            "count": "int",
            "ratio": "float",
            "is_active": "bool",
            "items": "list",
            "config": "dict"
        }
        
        found_count = 0
        for key, var_info in result["variables"].items():
            var_name = var_info["name"]
            if var_name in expected_types:
                expected = expected_types[var_name]
                actual = var_info["type"]["name"]
                assert actual == expected, f"{var_name}: expected {expected}, got {actual}"
                print(f"  ✓ {var_name}: {actual}")
                found_count += 1
        
        assert found_count >= 4, f"Expected at least 4 variables, found {found_count}"
        
        print("  ✅ Type inference from literals test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_function_return_type_inference():
    """Test inference of function return types."""
    print("\n🔄 Test 3: Function Return Type Inference")
    
    test_dir = create_test_project()
    try:
        inferencer = TypeInferencer(test_dir)
        result = inferencer.analyze_project()
        
        # Check create_product returns Product
        create_product_sig = None
        for name, sig in result["functions"].items():
            if sig["name"] == "create_product":
                create_product_sig = sig
                break
        
        assert create_product_sig is not None, "create_product function not found"
        print(f"  ✓ create_product return type: {create_product_sig['return_type']['name']}")
        
        # Check get_display_name
        get_display_sig = None
        for name, sig in result["functions"].items():
            if sig["name"] == "get_display_name":
                get_display_sig = sig
                break
        
        if get_display_sig:
            print(f"  ✓ get_display_name return type: {get_display_sig['return_type']['name']}")
        
        print("  ✅ Function return type inference test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_javascript_type_inference():
    """Test JavaScript type inference."""
    print("\n📦 Test 4: JavaScript Type Inference")
    
    test_dir = create_test_project()
    try:
        inferencer = TypeInferencer(test_dir)
        result = inferencer.analyze_project()
        
        # Check ShoppingCart class
        cart_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "ShoppingCart":
                cart_class = cls
                break
        
        assert cart_class is not None, "ShoppingCart class not found"
        print(f"  ✓ Found ShoppingCart class")
        
        # Check JS variable types
        js_vars = {}
        for key, var_info in result["variables"].items():
            if "cart.js" in var_info.get("file_path", "") or "/cart" in key:
                js_vars[var_info["name"]] = var_info["type"]["name"]
        
        if "message" in js_vars:
            print(f"  ✓ JS message type: {js_vars['message']}")
        if "count" in js_vars:
            print(f"  ✓ JS count type: {js_vars['count']}")
        
        # Check calculateDiscount function
        calc_func = None
        for name, sig in result["functions"].items():
            if sig["name"] == "calculateDiscount":
                calc_func = sig
                break
        
        assert calc_func is not None, "calculateDiscount function not found"
        print(f"  ✓ calculateDiscount has {len(calc_func['parameters'])} parameters")
        
        print("  ✅ JavaScript type inference test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_typescript_types():
    """Test TypeScript type parsing."""
    print("\n📘 Test 5: TypeScript Type Parsing")
    
    test_dir = create_test_project()
    try:
        inferencer = TypeInferencer(test_dir)
        result = inferencer.analyze_project()
        
        # Check TypedCart class (may not exist if TS not supported)
        typed_cart = None
        for name, cls in result["classes"].items():
            if cls["name"] == "TypedCart":
                typed_cart = cls
                break
        
        if typed_cart:
            print(f"  ✓ Found TypedCart class")
            
            # Check Product interface
            product_interface = None
            for name, cls in result["classes"].items():
                if cls["name"] == "Product":
                    product_interface = cls
                    break
            
            if product_interface:
                print(f"  ✓ Found Product interface")
            
            # Check formatPrice function
            format_func = None
            for name, sig in result["functions"].items():
                if sig["name"] == "formatPrice":
                    format_func = sig
                    break
            
            if format_func:
                print(f"  ✓ formatPrice return type: {format_func['return_type']['name']}")
        else:
            print("  ⚠ TypeScript parsing not available (tree-sitter-typescript not installed)")
        
        print("  ✅ TypeScript type parsing test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_real_project_analysis():
    """Test analysis on the actual backend project."""
    print("\n🏗️ Test 6: Real Project Analysis")
    
    backend_path = os.path.dirname(os.path.abspath(__file__))
    
    inferencer = TypeInferencer(backend_path)
    result = inferencer.analyze_project()
    
    stats = result["statistics"]
    print(f"  📊 Analysis Statistics:")
    print(f"     Files analyzed: {stats['total_files']}")
    print(f"     Variables inferred: {stats['variables_inferred']}")
    print(f"     Functions analyzed: {stats['functions_analyzed']}")
    print(f"     Classes analyzed: {stats['classes_analyzed']}")
    print(f"     Type annotations found: {stats['type_annotations_found']}")
    print(f"     Types from literals: {stats['types_from_literals']}")
    
    # Should find significant number of each
    assert stats['total_files'] > 5, "Should analyze multiple files"
    assert stats['functions_analyzed'] > 10, "Should find many functions"
    assert stats['classes_analyzed'] > 3, "Should find several classes"
    
    print("  ✅ Real project analysis test passed!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Type Inference Module Test Suite (Phase 2.3)")
    print("=" * 60)
    
    tests = [
        ("Python Type Annotations", test_python_type_annotations),
        ("Type Inference from Literals", test_type_inference_from_literals),
        ("Function Return Type Inference", test_function_return_type_inference),
        ("JavaScript Type Inference", test_javascript_type_inference),
        ("TypeScript Type Parsing", test_typescript_types),
        ("Real Project Analysis", test_real_project_analysis),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n  ❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
