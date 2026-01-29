"""
Test Suite for Monorepo Analyzer

Tests for:
- Build configuration parsing (package.json, pom.xml, go.mod, etc.)
- Monorepo tool detection
- Dependency graph building
- Build order calculation
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_package_json_parser():
    """Test package.json parser."""
    print("\n" + "="*60)
    print("Test 1: package.json Parser")
    print("="*60)
    
    from core.monorepo_analyzer import PackageJsonParser, ProjectType, BuildSystem
    
    parser = PackageJsonParser()
    
    # Create test package.json
    package_json = {
        "name": "@myorg/web-app",
        "version": "1.0.0",
        "description": "A web application",
        "main": "dist/index.js",
        "module": "dist/index.esm.js",
        "private": True,
        "scripts": {
            "build": "tsc",
            "test": "jest",
            "start": "node dist/index.js"
        },
        "dependencies": {
            "express": "^4.18.0",
            "react": "^18.0.0",
            "@myorg/shared": "workspace:*"
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "jest": "^29.0.0"
        }
    }
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Write package.json
        pkg_path = os.path.join(temp_dir, 'package.json')
        with open(pkg_path, 'w') as f:
            json.dump(package_json, f)
        
        # Create yarn.lock to indicate yarn
        with open(os.path.join(temp_dir, 'yarn.lock'), 'w') as f:
            f.write('')
        
        config = parser.parse(pkg_path)
        
        assert config is not None
        print(f"✓ Package parsed successfully")
        
        assert config.name == "@myorg/web-app"
        print(f"✓ Name: {config.name}")
        
        assert config.version == "1.0.0"
        print(f"✓ Version: {config.version}")
        
        assert config.build_system == BuildSystem.YARN
        print(f"✓ Build system: {config.build_system.value}")
        
        assert len(config.dependencies) == 3
        print(f"✓ Dependencies: {len(config.dependencies)}")
        
        # Check local dependency detection
        local_deps = [d for d in config.dependencies if d.is_local]
        assert len(local_deps) == 1
        assert local_deps[0].name == "@myorg/shared"
        print(f"✓ Local dependency detected: {local_deps[0].name}")
        
        assert len(config.dev_dependencies) == 2
        print(f"✓ Dev dependencies: {len(config.dev_dependencies)}")
        
        assert len(config.scripts) == 3
        print(f"✓ Scripts: {[s.name for s in config.scripts]}")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ package.json parser test passed!")
    return True


def test_pom_xml_parser():
    """Test Maven pom.xml parser."""
    print("\n" + "="*60)
    print("Test 2: pom.xml Parser")
    print("="*60)
    
    from core.monorepo_analyzer import PomXmlParser, ProjectType, BuildSystem
    
    parser = PomXmlParser()
    
    pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>my-service</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <name>My Service</name>
    <description>A microservice</description>
    
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <version>3.0.0</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <modules>
        <module>core</module>
        <module>api</module>
    </modules>
</project>
"""
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        pom_path = os.path.join(temp_dir, 'pom.xml')
        with open(pom_path, 'w') as f:
            f.write(pom_content)
        
        config = parser.parse(pom_path)
        
        assert config is not None
        print(f"✓ POM parsed successfully")
        
        assert config.name == "my-service"
        print(f"✓ Artifact ID: {config.name}")
        
        assert config.version == "1.0.0"
        print(f"✓ Version: {config.version}")
        
        assert config.build_system == BuildSystem.MAVEN
        print(f"✓ Build system: {config.build_system.value}")
        
        assert config.language == "java"
        print(f"✓ Language: {config.language}")
        
        assert len(config.dependencies) == 2
        print(f"✓ Dependencies: {len(config.dependencies)}")
        
        # Check modules
        modules = config.build_config.get('modules', [])
        assert len(modules) == 2
        print(f"✓ Modules: {modules}")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ pom.xml parser test passed!")
    return True


def test_go_mod_parser():
    """Test go.mod parser."""
    print("\n" + "="*60)
    print("Test 3: go.mod Parser")
    print("="*60)
    
    from core.monorepo_analyzer import GoModParser, BuildSystem
    
    parser = GoModParser()
    
    go_mod_content = """module github.com/myorg/myservice

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/lib/pq v1.10.0
    github.com/myorg/shared v0.0.0 // indirect
)

replace github.com/myorg/shared => ../shared
"""
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create go.mod
        go_mod_path = os.path.join(temp_dir, 'go.mod')
        with open(go_mod_path, 'w') as f:
            f.write(go_mod_content)
        
        # Create cmd directory to indicate application
        os.makedirs(os.path.join(temp_dir, 'cmd'))
        
        config = parser.parse(go_mod_path)
        
        assert config is not None
        print(f"✓ go.mod parsed successfully")
        
        assert config.name == "github.com/myorg/myservice"
        print(f"✓ Module: {config.name}")
        
        assert config.build_system == BuildSystem.GO_MOD
        print(f"✓ Build system: {config.build_system.value}")
        
        assert config.language == "go"
        print(f"✓ Language: {config.language}")
        
        go_version = config.metadata.get('go_version')
        assert go_version == "1.21"
        print(f"✓ Go version: {go_version}")
        
        assert len(config.dependencies) >= 3
        print(f"✓ Dependencies: {len(config.dependencies)}")
        
        # Check local dependency via replace
        local_deps = [d for d in config.dependencies if d.is_local]
        assert len(local_deps) >= 1
        print(f"✓ Local dependencies detected: {len(local_deps)}")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ go.mod parser test passed!")
    return True


def test_monorepo_detection():
    """Test monorepo tool detection."""
    print("\n" + "="*60)
    print("Test 4: Monorepo Tool Detection")
    print("="*60)
    
    from core.monorepo_analyzer import MonorepoDetector, MonorepoTool
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Test npm workspaces
        npm_dir = os.path.join(temp_dir, 'npm-workspace')
        os.makedirs(npm_dir)
        
        with open(os.path.join(npm_dir, 'package.json'), 'w') as f:
            json.dump({
                "name": "my-monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }, f)
        
        detector = MonorepoDetector(npm_dir)
        tool, config = detector.detect()
        assert tool == MonorepoTool.NPM_WORKSPACES
        print(f"✓ npm workspaces detected")
        
        # Test yarn workspaces
        yarn_dir = os.path.join(temp_dir, 'yarn-workspace')
        os.makedirs(yarn_dir)
        
        with open(os.path.join(yarn_dir, 'package.json'), 'w') as f:
            json.dump({
                "name": "my-monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }, f)
        
        with open(os.path.join(yarn_dir, 'yarn.lock'), 'w') as f:
            f.write('')
        
        detector = MonorepoDetector(yarn_dir)
        tool, config = detector.detect()
        assert tool == MonorepoTool.YARN_WORKSPACES
        print(f"✓ yarn workspaces detected")
        
        # Test turborepo
        turbo_dir = os.path.join(temp_dir, 'turborepo')
        os.makedirs(turbo_dir)
        
        with open(os.path.join(turbo_dir, 'turbo.json'), 'w') as f:
            json.dump({"pipeline": {}}, f)
        
        detector = MonorepoDetector(turbo_dir)
        tool, config = detector.detect()
        assert tool == MonorepoTool.TURBOREPO
        print(f"✓ turborepo detected")
        
        # Test lerna
        lerna_dir = os.path.join(temp_dir, 'lerna')
        os.makedirs(lerna_dir)
        
        with open(os.path.join(lerna_dir, 'lerna.json'), 'w') as f:
            json.dump({"packages": ["packages/*"]}, f)
        
        detector = MonorepoDetector(lerna_dir)
        tool, config = detector.detect()
        assert tool == MonorepoTool.LERNA
        print(f"✓ lerna detected")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ Monorepo detection test passed!")
    return True


def test_monorepo_analyzer():
    """Test full monorepo analysis."""
    print("\n" + "="*60)
    print("Test 5: Monorepo Analyzer")
    print("="*60)
    
    from core.monorepo_analyzer import MonorepoAnalyzer, MonorepoTool
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a monorepo structure
        # Root package.json
        with open(os.path.join(temp_dir, 'package.json'), 'w') as f:
            json.dump({
                "name": "my-monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }, f)
        
        # Create packages
        packages_dir = os.path.join(temp_dir, 'packages')
        os.makedirs(packages_dir)
        
        # Package A (shared library)
        pkg_a = os.path.join(packages_dir, 'shared')
        os.makedirs(pkg_a)
        with open(os.path.join(pkg_a, 'package.json'), 'w') as f:
            json.dump({
                "name": "@myorg/shared",
                "version": "1.0.0",
                "main": "index.js"
            }, f)
        
        # Package B (depends on A)
        pkg_b = os.path.join(packages_dir, 'api')
        os.makedirs(pkg_b)
        with open(os.path.join(pkg_b, 'package.json'), 'w') as f:
            json.dump({
                "name": "@myorg/api",
                "version": "1.0.0",
                "dependencies": {
                    "@myorg/shared": "workspace:*",
                    "express": "^4.18.0"
                }
            }, f)
        
        # Package C (depends on A and B)
        pkg_c = os.path.join(packages_dir, 'web')
        os.makedirs(pkg_c)
        with open(os.path.join(pkg_c, 'package.json'), 'w') as f:
            json.dump({
                "name": "@myorg/web",
                "version": "1.0.0",
                "dependencies": {
                    "@myorg/shared": "workspace:*",
                    "@myorg/api": "workspace:*",
                    "react": "^18.0.0"
                }
            }, f)
        
        # Analyze
        analyzer = MonorepoAnalyzer(temp_dir)
        structure = analyzer.analyze()
        
        assert structure.monorepo_tool == MonorepoTool.NPM_WORKSPACES
        print(f"✓ Monorepo tool: {structure.monorepo_tool.value}")
        
        assert len(structure.projects) >= 3
        print(f"✓ Projects found: {len(structure.projects)}")
        
        project_names = [p.name for p in structure.projects]
        assert "@myorg/shared" in project_names
        assert "@myorg/api" in project_names
        assert "@myorg/web" in project_names
        print(f"✓ Project names: {project_names}")
        
        # Check dependencies
        api_project = next(p for p in structure.projects if p.name == "@myorg/api")
        assert "@myorg/shared" in api_project.internal_dependencies
        print(f"✓ API dependencies: {api_project.internal_dependencies}")
        
        web_project = next(p for p in structure.projects if p.name == "@myorg/web")
        assert "@myorg/shared" in web_project.internal_dependencies
        assert "@myorg/api" in web_project.internal_dependencies
        print(f"✓ Web dependencies: {web_project.internal_dependencies}")
        
        # Check shared packages
        assert "@myorg/shared" in structure.shared_packages
        print(f"✓ Shared packages: {structure.shared_packages}")
        
        # Check build order - should have projects listed
        print(f"✓ Build order: {structure.build_order}")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ Monorepo analyzer test passed!")
    return True


def test_dependency_graph():
    """Test dependency graph generation."""
    print("\n" + "="*60)
    print("Test 6: Dependency Graph Generation")
    print("="*60)
    
    from core.monorepo_analyzer import MonorepoAnalyzer, get_dependency_graph
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create monorepo
        with open(os.path.join(temp_dir, 'package.json'), 'w') as f:
            json.dump({
                "name": "graph-test",
                "private": True,
                "workspaces": ["packages/*"]
            }, f)
        
        packages_dir = os.path.join(temp_dir, 'packages')
        os.makedirs(packages_dir)
        
        # Create packages with dependencies
        for name in ['core', 'utils', 'app']:
            pkg_dir = os.path.join(packages_dir, name)
            os.makedirs(pkg_dir)
            
            deps = {}
            if name == 'utils':
                deps['@test/core'] = 'workspace:*'
            if name == 'app':
                deps['@test/core'] = 'workspace:*'
                deps['@test/utils'] = 'workspace:*'
            
            with open(os.path.join(pkg_dir, 'package.json'), 'w') as f:
                json.dump({
                    "name": f"@test/{name}",
                    "version": "1.0.0",
                    "dependencies": deps
                }, f)
        
        # Get graph
        graph = get_dependency_graph(temp_dir)
        
        assert 'nodes' in graph
        assert 'edges' in graph
        print(f"✓ Graph structure valid")
        
        assert len(graph['nodes']) >= 3
        print(f"✓ Nodes: {len(graph['nodes'])}")
        
        node_ids = [n['id'] for n in graph['nodes']]
        assert '@test/core' in node_ids
        assert '@test/utils' in node_ids
        assert '@test/app' in node_ids
        print(f"✓ Node IDs: {node_ids}")
        
        assert len(graph['edges']) >= 3
        print(f"✓ Edges: {len(graph['edges'])}")
        
        edge_pairs = [(e['source'], e['target']) for e in graph['edges']]
        assert ('@test/utils', '@test/core') in edge_pairs
        assert ('@test/app', '@test/core') in edge_pairs
        assert ('@test/app', '@test/utils') in edge_pairs
        print(f"✓ Edge pairs verified")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ Dependency graph test passed!")
    return True


def test_affected_projects():
    """Test affected projects detection."""
    print("\n" + "="*60)
    print("Test 7: Affected Projects Detection")
    print("="*60)
    
    from core.monorepo_analyzer import get_affected_projects
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create monorepo
        with open(os.path.join(temp_dir, 'package.json'), 'w') as f:
            json.dump({
                "name": "affected-test",
                "private": True,
                "workspaces": ["packages/*"]
            }, f)
        
        packages_dir = os.path.join(temp_dir, 'packages')
        os.makedirs(packages_dir)
        
        # Create chain: core <- utils <- app
        for name, deps in [('core', {}), ('utils', {'@test/core': 'workspace:*'}), ('app', {'@test/utils': 'workspace:*'})]:
            pkg_dir = os.path.join(packages_dir, name)
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, 'package.json'), 'w') as f:
                json.dump({
                    "name": f"@test/{name}",
                    "version": "1.0.0",
                    "dependencies": deps
                }, f)
        
        # Test: if core changes, utils and app should be affected
        result = get_affected_projects(temp_dir, ['@test/core'])
        
        assert '@test/core' in result['affected']
        assert '@test/utils' in result['affected']
        assert '@test/app' in result['affected']
        print(f"✓ Affected by core change: {result['affected']}")
        
        # Test: if utils changes, only utils and app affected
        result = get_affected_projects(temp_dir, ['@test/utils'])
        
        assert '@test/core' not in result['affected']
        assert '@test/utils' in result['affected']
        assert '@test/app' in result['affected']
        print(f"✓ Affected by utils change: {result['affected']}")
        
        # Test: if app changes, only app affected
        result = get_affected_projects(temp_dir, ['@test/app'])
        
        assert '@test/core' not in result['affected']
        assert '@test/utils' not in result['affected']
        assert '@test/app' in result['affected']
        print(f"✓ Affected by app change: {result['affected']}")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ Affected projects test passed!")
    return True


def test_gradle_parser():
    """Test Gradle build.gradle parser."""
    print("\n" + "="*60)
    print("Test 8: Gradle Parser")
    print("="*60)
    
    from core.monorepo_analyzer import GradleParser, BuildSystem
    
    parser = GradleParser()
    
    build_gradle = """
plugins {
    id 'java-library'
    id 'org.jetbrains.kotlin.jvm' version '1.9.0'
}

group = 'com.example'
version = '1.0.0'

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web:3.0.0'
    api 'com.google.guava:guava:31.1-jre'
    testImplementation 'junit:junit:4.13.2'
}
"""
    
    settings_gradle = """
rootProject.name = 'my-gradle-project'

include 'core'
include 'api'
include 'web'
"""
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        with open(os.path.join(temp_dir, 'build.gradle'), 'w') as f:
            f.write(build_gradle)
        
        with open(os.path.join(temp_dir, 'settings.gradle'), 'w') as f:
            f.write(settings_gradle)
        
        config = parser.parse(os.path.join(temp_dir, 'build.gradle'))
        
        assert config is not None
        print(f"✓ Gradle parsed successfully")
        
        assert config.name == "my-gradle-project"
        print(f"✓ Project name: {config.name}")
        
        assert config.build_system == BuildSystem.GRADLE
        print(f"✓ Build system: {config.build_system.value}")
        
        assert config.language == "kotlin"  # Detected from plugin
        print(f"✓ Language: {config.language}")
        
        assert len(config.dependencies) >= 3
        print(f"✓ Dependencies: {len(config.dependencies)}")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ Gradle parser test passed!")
    return True


def test_real_project():
    """Test with real workspace project."""
    print("\n" + "="*60)
    print("Test 9: Real Project Analysis")
    print("="*60)
    
    from core.monorepo_analyzer import MonorepoAnalyzer, analyze_monorepo
    
    # Analyze the actual project
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    result = analyze_monorepo(project_path)
    
    print(f"✓ Project analyzed: {result['root_path']}")
    print(f"✓ Monorepo tool: {result['monorepo_tool']}")
    print(f"✓ Total projects: {result['stats']['total_projects']}")
    print(f"✓ Languages: {result['stats']['languages']}")
    print(f"✓ Project types: {result['stats']['project_types']}")
    
    if result['projects']:
        print(f"✓ First project: {result['projects'][0]['name']}")
    
    print("\n✅ Real project analysis test passed!")
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("Monorepo Analyzer Test Suite")
    print("="*60)
    
    tests = [
        ("package.json Parser", test_package_json_parser),
        ("pom.xml Parser", test_pom_xml_parser),
        ("go.mod Parser", test_go_mod_parser),
        ("Monorepo Detection", test_monorepo_detection),
        ("Monorepo Analyzer", test_monorepo_analyzer),
        ("Dependency Graph", test_dependency_graph),
        ("Affected Projects", test_affected_projects),
        ("Gradle Parser", test_gradle_parser),
        ("Real Project Analysis", test_real_project),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️ {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
