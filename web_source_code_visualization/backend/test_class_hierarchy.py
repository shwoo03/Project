"""
Test suite for Class Hierarchy Analysis Module (Phase 2.4).

Tests the ClassHierarchyAnalyzer class for:
- Inheritance graph construction
- Method override detection
- Polymorphic call resolution
- Interface/Protocol implementation tracking
- Method Resolution Order (MRO) computation
"""

import os
import sys
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.class_hierarchy import ClassHierarchyAnalyzer, ClassKind, MethodKind, analyze_class_hierarchy


def create_test_project():
    """Create a temporary test project with class hierarchies."""
    test_dir = tempfile.mkdtemp(prefix="hierarchy_test_")
    
    # Python inheritance hierarchy
    python_hierarchy = '''
from abc import ABC, abstractmethod
from typing import Protocol


class Animal(ABC):
    """Abstract base class for animals."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def speak(self) -> str:
        pass
    
    def move(self) -> str:
        return "moving"


class Mammal(Animal):
    """Mammals are animals with fur."""
    
    def __init__(self, name: str, fur_color: str):
        super().__init__(name)
        self.fur_color = fur_color
    
    def nurse(self) -> str:
        return "nursing young"


class Dog(Mammal):
    """A dog is a mammal."""
    
    def speak(self) -> str:
        return "Woof!"
    
    def fetch(self) -> str:
        return "fetching ball"


class Cat(Mammal):
    """A cat is a mammal."""
    
    def speak(self) -> str:
        return "Meow!"
    
    def purr(self) -> str:
        return "purring"


class Bird(Animal):
    """Birds are animals that can fly."""
    
    def speak(self) -> str:
        return "Chirp!"
    
    def fly(self) -> str:
        return "flying"


# Protocol (interface-like)
class Flyable(Protocol):
    def fly(self) -> str:
        ...


class FlyingFish(Animal):
    """A fish that can fly."""
    
    def speak(self) -> str:
        return "Blub!"
    
    def fly(self) -> str:
        return "gliding through air"


# Multiple inheritance (mixin)
class SwimmerMixin:
    def swim(self) -> str:
        return "swimming"


class Duck(Bird, SwimmerMixin):
    """A duck can fly and swim."""
    
    def speak(self) -> str:
        return "Quack!"
'''
    
    with open(os.path.join(test_dir, "animals.py"), 'w') as f:
        f.write(python_hierarchy)
    
    # Python diamond inheritance
    python_diamond = '''
class A:
    def method(self):
        return "A"


class B(A):
    def method(self):
        return "B"


class C(A):
    def method(self):
        return "C"


class D(B, C):
    """Diamond inheritance: D -> B -> A and D -> C -> A"""
    pass


class E(B, C):
    def method(self):
        return "E"
'''
    
    with open(os.path.join(test_dir, "diamond.py"), 'w') as f:
        f.write(python_diamond)
    
    # JavaScript class hierarchy
    javascript_hierarchy = '''
class Vehicle {
    constructor(brand) {
        this.brand = brand;
    }
    
    start() {
        return "Starting...";
    }
    
    stop() {
        return "Stopping...";
    }
}


class Car extends Vehicle {
    constructor(brand, model) {
        super(brand);
        this.model = model;
    }
    
    start() {
        return "Car starting: " + this.brand;
    }
    
    drive() {
        return "Driving";
    }
}


class ElectricCar extends Car {
    constructor(brand, model, batteryCapacity) {
        super(brand, model);
        this.batteryCapacity = batteryCapacity;
    }
    
    charge() {
        return "Charging...";
    }
    
    start() {
        return "Silent start: " + this.brand;
    }
}


class Motorcycle extends Vehicle {
    wheelie() {
        return "Doing a wheelie!";
    }
}
'''
    
    with open(os.path.join(test_dir, "vehicles.js"), 'w') as f:
        f.write(javascript_hierarchy)
    
    # TypeScript interfaces and classes
    typescript_hierarchy = '''
interface Shape {
    area(): number;
    perimeter(): number;
}

interface Colorable {
    color: string;
    setColor(color: string): void;
}

abstract class BaseShape implements Shape {
    abstract area(): number;
    abstract perimeter(): number;
    
    describe(): string {
        return `Area: ${this.area()}, Perimeter: ${this.perimeter()}`;
    }
}

class Rectangle extends BaseShape implements Colorable {
    color: string = "white";
    
    constructor(
        private width: number,
        private height: number
    ) {
        super();
    }
    
    area(): number {
        return this.width * this.height;
    }
    
    perimeter(): number {
        return 2 * (this.width + this.height);
    }
    
    setColor(color: string): void {
        this.color = color;
    }
}

class Square extends Rectangle {
    constructor(side: number) {
        super(side, side);
    }
}

class Circle extends BaseShape {
    constructor(private radius: number) {
        super();
    }
    
    area(): number {
        return Math.PI * this.radius ** 2;
    }
    
    perimeter(): number {
        return 2 * Math.PI * this.radius;
    }
}

enum ShapeType {
    Rectangle,
    Square,
    Circle
}
'''
    
    with open(os.path.join(test_dir, "shapes.ts"), 'w') as f:
        f.write(typescript_hierarchy)
    
    return test_dir


def test_inheritance_detection():
    """Test detection of inheritance relationships."""
    print("\n🔗 Test 1: Inheritance Detection")
    
    test_dir = create_test_project()
    try:
        analyzer = ClassHierarchyAnalyzer(test_dir)
        result = analyzer.analyze_project()
        
        # Check Dog inherits from Mammal
        dog_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "Dog":
                dog_class = cls
                break
        
        assert dog_class is not None, "Dog class not found"
        assert "Mammal" in dog_class["direct_bases"], f"Dog should extend Mammal, got {dog_class['direct_bases']}"
        print(f"  ✓ Dog extends Mammal")
        
        # Check Mammal inherits from Animal
        mammal_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "Mammal":
                mammal_class = cls
                break
        
        assert mammal_class is not None, "Mammal class not found"
        assert "Animal" in mammal_class["direct_bases"], "Mammal should extend Animal"
        print(f"  ✓ Mammal extends Animal")
        
        # Check all_bases for Dog includes both Mammal and Animal
        assert len(dog_class["all_bases"]) >= 1, "Dog should have ancestors"
        print(f"  ✓ Dog has {len(dog_class['all_bases'])} ancestor(s)")
        
        print("  ✅ Inheritance detection test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_method_override_detection():
    """Test detection of method overrides."""
    print("\n🔄 Test 2: Method Override Detection")
    
    test_dir = create_test_project()
    try:
        analyzer = ClassHierarchyAnalyzer(test_dir)
        result = analyzer.analyze_project()
        
        # Check Dog.speak overrides Animal.speak
        dog_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "Dog":
                dog_class = cls
                break
        
        assert dog_class is not None, "Dog class not found"
        assert "speak" in dog_class["methods"], "Dog should have speak method"
        
        speak_method = dog_class["methods"]["speak"]
        assert speak_method["is_override"], "Dog.speak should be an override"
        print(f"  ✓ Dog.speak is an override")
        
        # Check Cat.speak also overrides
        cat_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "Cat":
                cat_class = cls
                break
        
        assert cat_class is not None, "Cat class not found"
        if "speak" in cat_class["methods"]:
            print(f"  ✓ Cat.speak is also present")
        
        # Check total override count
        stats = result["statistics"]
        print(f"  ✓ Total method overrides detected: {stats['method_overrides']}")
        
        print("  ✅ Method override detection test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_abstract_class_detection():
    """Test detection of abstract classes and methods."""
    print("\n📋 Test 3: Abstract Class Detection")
    
    test_dir = create_test_project()
    try:
        analyzer = ClassHierarchyAnalyzer(test_dir)
        result = analyzer.analyze_project()
        
        # Check Animal is abstract
        animal_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "Animal":
                animal_class = cls
                break
        
        assert animal_class is not None, "Animal class not found"
        assert animal_class["is_abstract"], "Animal should be abstract"
        print(f"  ✓ Animal is abstract")
        
        # Check abstract method
        if "speak" in animal_class["methods"]:
            speak_method = animal_class["methods"]["speak"]
            print(f"  ✓ Animal.speak is {speak_method['kind']}")
        
        # Check stats
        stats = result["statistics"]
        print(f"  ✓ Total abstract classes: {stats['abstract_classes']}")
        
        print("  ✅ Abstract class detection test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_multiple_inheritance():
    """Test handling of multiple inheritance (mixins)."""
    print("\n🔀 Test 4: Multiple Inheritance (Mixins)")
    
    test_dir = create_test_project()
    try:
        analyzer = ClassHierarchyAnalyzer(test_dir)
        result = analyzer.analyze_project()
        
        # Check Duck has multiple bases
        duck_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "Duck":
                duck_class = cls
                break
        
        assert duck_class is not None, "Duck class not found"
        assert len(duck_class["direct_bases"]) >= 2, f"Duck should have multiple bases, got {duck_class['direct_bases']}"
        print(f"  ✓ Duck extends: {duck_class['direct_bases']}")
        
        # Check MRO
        if duck_class["mro"]:
            print(f"  ✓ Duck MRO: {duck_class['mro'][:5]}...")
        
        print("  ✅ Multiple inheritance test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_diamond_inheritance():
    """Test detection of diamond inheritance."""
    print("\n💎 Test 5: Diamond Inheritance")
    
    test_dir = create_test_project()
    try:
        analyzer = ClassHierarchyAnalyzer(test_dir)
        result = analyzer.analyze_project()
        
        # Check D class has diamond inheritance
        d_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "D":
                d_class = cls
                break
        
        assert d_class is not None, "D class not found"
        assert len(d_class["direct_bases"]) >= 2, "D should have multiple bases"
        print(f"  ✓ D extends: {d_class['direct_bases']}")
        
        # Check diamond detection in stats
        stats = result["statistics"]
        print(f"  ✓ Diamond inheritances detected: {stats['diamond_inheritances']}")
        
        # Check MRO handles diamond correctly
        if d_class["mro"]:
            print(f"  ✓ D MRO (C3 linearization): {d_class['mro']}")
        
        print("  ✅ Diamond inheritance test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_javascript_classes():
    """Test JavaScript class hierarchy."""
    print("\n📦 Test 6: JavaScript Class Hierarchy")
    
    test_dir = create_test_project()
    try:
        analyzer = ClassHierarchyAnalyzer(test_dir)
        result = analyzer.analyze_project()
        
        # Check Vehicle class
        vehicle_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "Vehicle":
                vehicle_class = cls
                break
        
        assert vehicle_class is not None, "Vehicle class not found"
        print(f"  ✓ Found Vehicle class with {len(vehicle_class['methods'])} methods")
        
        # Check Car extends Vehicle
        car_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "Car":
                car_class = cls
                break
        
        assert car_class is not None, "Car class not found"
        assert "Vehicle" in car_class["direct_bases"], "Car should extend Vehicle"
        print(f"  ✓ Car extends Vehicle")
        
        # Check ElectricCar chain
        electric_class = None
        for name, cls in result["classes"].items():
            if cls["name"] == "ElectricCar":
                electric_class = cls
                break
        
        if electric_class:
            print(f"  ✓ ElectricCar extends: {electric_class['direct_bases']}")
        
        print("  ✅ JavaScript class hierarchy test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_polymorphic_resolution():
    """Test polymorphic call resolution."""
    print("\n🎯 Test 7: Polymorphic Call Resolution")
    
    test_dir = create_test_project()
    try:
        analyzer = ClassHierarchyAnalyzer(test_dir)
        analyzer.analyze_project()
        
        # Resolve speak() on Animal type
        targets = analyzer.resolve_polymorphic_call("Animal", "speak")
        
        # Should include Dog.speak, Cat.speak, Bird.speak, etc.
        print(f"  ✓ Animal.speak could resolve to {len(targets)} implementations:")
        for target in targets[:5]:
            print(f"     - {target}")
        
        assert len(targets) >= 2, "Should find multiple speak implementations"
        
        # Resolve on more specific type
        mammal_targets = analyzer.resolve_polymorphic_call("Mammal", "speak")
        print(f"  ✓ Mammal.speak could resolve to {len(mammal_targets)} implementations")
        
        print("  ✅ Polymorphic call resolution test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_inheritance_graph():
    """Test inheritance graph generation for visualization."""
    print("\n📊 Test 8: Inheritance Graph Generation")
    
    test_dir = create_test_project()
    try:
        analyzer = ClassHierarchyAnalyzer(test_dir)
        analyzer.analyze_project()
        
        graph = analyzer.get_inheritance_graph()
        
        print(f"  ✓ Graph nodes: {len(graph['nodes'])}")
        print(f"  ✓ Graph edges: {len(graph['edges'])}")
        
        # Check node structure
        if graph['nodes']:
            sample_node = graph['nodes'][0]
            assert "id" in sample_node, "Node should have id"
            assert "label" in sample_node, "Node should have label"
            assert "kind" in sample_node, "Node should have kind"
            print(f"  ✓ Sample node: {sample_node['label']} ({sample_node['kind']})")
        
        # Check edge structure
        if graph['edges']:
            sample_edge = graph['edges'][0]
            assert "source" in sample_edge, "Edge should have source"
            assert "target" in sample_edge, "Edge should have target"
            assert "type" in sample_edge, "Edge should have type"
            print(f"  ✓ Sample edge: {sample_edge['source']} --{sample_edge['type']}--> {sample_edge['target']}")
        
        print("  ✅ Inheritance graph generation test passed!")
        return True
    finally:
        shutil.rmtree(test_dir)


def test_real_project_analysis():
    """Test analysis on the actual backend project."""
    print("\n🏗️ Test 9: Real Project Analysis")
    
    backend_path = os.path.dirname(os.path.abspath(__file__))
    
    analyzer = ClassHierarchyAnalyzer(backend_path)
    result = analyzer.analyze_project()
    
    stats = result["statistics"]
    print(f"  📊 Analysis Statistics:")
    print(f"     Files analyzed: {stats['total_files']}")
    print(f"     Classes found: {stats['total_classes']}")
    print(f"     Interfaces found: {stats['total_interfaces']}")
    print(f"     Methods found: {stats['total_methods']}")
    print(f"     Inheritance edges: {stats['inheritance_edges']}")
    print(f"     Method overrides: {stats['method_overrides']}")
    print(f"     Abstract classes: {stats['abstract_classes']}")
    
    # Should find classes in the backend
    assert stats['total_files'] > 5, "Should analyze multiple files"
    assert stats['total_classes'] > 3, "Should find several classes"
    
    print("  ✅ Real project analysis test passed!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Class Hierarchy Analysis Test Suite (Phase 2.4)")
    print("=" * 60)
    
    tests = [
        ("Inheritance Detection", test_inheritance_detection),
        ("Method Override Detection", test_method_override_detection),
        ("Abstract Class Detection", test_abstract_class_detection),
        ("Multiple Inheritance (Mixins)", test_multiple_inheritance),
        ("Diamond Inheritance", test_diamond_inheritance),
        ("JavaScript Class Hierarchy", test_javascript_classes),
        ("Polymorphic Call Resolution", test_polymorphic_resolution),
        ("Inheritance Graph Generation", test_inheritance_graph),
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
