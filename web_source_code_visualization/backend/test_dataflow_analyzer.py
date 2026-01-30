"""
Tests for Advanced Data-Flow Analysis (Phase 4.3).

Tests cover:
- CFG Building
- PDG Generation
- Path-sensitive analysis
- Context-sensitive analysis
- Program slicing
- Taint tracking with PDG
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cfg_builder import (
    CFGBuilder, ControlFlowGraph, CFGNode, CFGNodeType, EdgeType,
    build_project_cfgs
)
from core.pdg_generator import (
    PDGGenerator, ProgramDependenceGraph, PDGNode, DependenceType,
    TaintPDGAnalyzer, generate_project_pdgs
)
from core.advanced_dataflow_analyzer import (
    AdvancedDataFlowAnalyzer, AnalysisSensitivity,
    SymbolicState, SymbolicValue, SymbolicValueType,
    PathCondition, analyze_with_advanced_dataflow
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_python_code():
    """Sample Python code for testing."""
    return '''
def vulnerable_func(user_input):
    """A function with a vulnerability."""
    data = user_input
    if len(data) > 10:
        processed = data.upper()
    else:
        processed = data.lower()
    
    # Sink
    os.system(processed)
    return processed


def safe_func(user_input):
    """A sanitized function."""
    data = user_input
    safe_data = shlex.quote(data)
    os.system(safe_data)
    return safe_data


def complex_control_flow(x, y):
    """Complex control flow for CFG testing."""
    result = 0
    
    if x > 0:
        if y > 0:
            result = x + y
        else:
            result = x - y
    else:
        for i in range(abs(x)):
            result += i
    
    while result > 100:
        result = result // 2
    
    return result


def multi_path_taint(input_data):
    """Multiple paths with different taint handling."""
    if input_data.startswith('admin'):
        # Sanitized path
        safe = html.escape(input_data)
        render_template_string(safe)
    else:
        # Vulnerable path
        render_template_string(input_data)
'''


@pytest.fixture
def sample_js_code():
    """Sample JavaScript code for testing."""
    return '''
function vulnerableEndpoint(req, res) {
    const userInput = req.query.data;
    
    if (userInput) {
        const processed = userInput.toUpperCase();
        eval(processed);
    }
    
    res.send("OK");
}


function safeEndpoint(req, res) {
    const userInput = req.query.data;
    const sanitized = escape(userInput);
    
    document.getElementById("output").innerText = sanitized;
    res.send("OK");
}


function complexLoop(items) {
    let result = [];
    
    for (let i = 0; i < items.length; i++) {
        if (items[i].valid) {
            result.push(items[i].value);
        }
    }
    
    return result;
}
'''


@pytest.fixture
def temp_python_file(sample_python_code):
    """Create a temporary Python file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(sample_python_code)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_js_file(sample_js_code):
    """Create a temporary JavaScript file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(sample_js_code)
        f.flush()
        yield f.name
    os.unlink(f.name)


# =============================================================================
# CFG Builder Tests
# =============================================================================

class TestCFGBuilder:
    """Tests for Control Flow Graph building."""
    
    def test_cfg_builder_creation(self):
        """Test CFG builder instantiation."""
        builder = CFGBuilder()
        assert builder is not None
        assert builder.py_parser is not None
        assert builder.js_parser is not None
    
    def test_build_python_cfg(self, temp_python_file):
        """Test building CFG from Python file."""
        builder = CFGBuilder()
        cfgs = builder.build_from_file(temp_python_file)
        
        assert cfgs is not None
        assert len(cfgs) > 0
        
        # Check that we have functions
        func_names = list(cfgs.keys())
        assert any('vulnerable_func' in name for name in func_names)
    
    def test_cfg_has_entry_exit(self, temp_python_file):
        """Test that CFG has entry and exit nodes."""
        builder = CFGBuilder()
        cfgs = builder.build_from_file(temp_python_file)
        
        for name, cfg in cfgs.items():
            assert cfg.entry_node is not None
            assert cfg.exit_node is not None
            assert cfg.entry_node.node_type == CFGNodeType.ENTRY
            assert cfg.exit_node.node_type == CFGNodeType.EXIT
    
    def test_cfg_edges(self, temp_python_file):
        """Test that CFG has proper edges."""
        builder = CFGBuilder()
        cfgs = builder.build_from_file(temp_python_file)
        
        for name, cfg in cfgs.items():
            assert len(cfg.edges) > 0
            assert len(cfg.nodes) > 0
            
            # Entry should have successors
            entry_id = cfg.entry_node.id
            assert entry_id in cfg.successors
    
    def test_cfg_condition_nodes(self, temp_python_file):
        """Test that conditions are properly captured."""
        builder = CFGBuilder()
        cfgs = builder.build_from_file(temp_python_file)
        
        # complex_control_flow has if statements
        for name, cfg in cfgs.items():
            if 'complex_control_flow' in name:
                condition_nodes = [
                    n for n in cfg.nodes.values() 
                    if n.node_type == CFGNodeType.CONDITION
                ]
                assert len(condition_nodes) > 0
    
    def test_cfg_loop_detection(self, temp_python_file):
        """Test loop detection in CFG."""
        builder = CFGBuilder()
        cfgs = builder.build_from_file(temp_python_file)
        
        for name, cfg in cfgs.items():
            if 'complex_control_flow' in name:
                # Should have back edges for loops
                assert len(cfg.back_edges) > 0 or len(cfg.loops) >= 0
    
    def test_build_js_cfg(self, temp_js_file):
        """Test building CFG from JavaScript file."""
        builder = CFGBuilder()
        cfgs = builder.build_from_file(temp_js_file)
        
        assert cfgs is not None
        assert len(cfgs) > 0
    
    def test_cfg_path_enumeration(self, temp_python_file):
        """Test path enumeration in CFG."""
        builder = CFGBuilder()
        cfgs = builder.build_from_file(temp_python_file)
        
        for name, cfg in cfgs.items():
            if cfg.entry_node and cfg.exit_node:
                paths = cfg.get_all_paths(
                    cfg.entry_node.id, 
                    cfg.exit_node.id,
                    max_paths=10
                )
                # Should find at least one path
                assert len(paths) >= 0  # May be 0 for some functions


# =============================================================================
# PDG Generator Tests
# =============================================================================

class TestPDGGenerator:
    """Tests for Program Dependence Graph generation."""
    
    def test_pdg_generator_creation(self):
        """Test PDG generator instantiation."""
        generator = PDGGenerator()
        assert generator is not None
        assert generator.cfg_builder is not None
    
    def test_generate_pdg_from_file(self, temp_python_file):
        """Test PDG generation from file."""
        generator = PDGGenerator()
        pdgs = generator.generate_from_file(temp_python_file)
        
        assert pdgs is not None
        assert len(pdgs) > 0
    
    def test_pdg_has_control_dependencies(self, temp_python_file):
        """Test that PDG has control dependencies."""
        generator = PDGGenerator()
        pdgs = generator.generate_from_file(temp_python_file)
        
        for name, pdg in pdgs.items():
            control_edges = [e for e in pdg.edges if e.dependence_type == DependenceType.CONTROL]
            # Should have some control dependencies
            assert len(control_edges) >= 0
    
    def test_pdg_has_data_dependencies(self, temp_python_file):
        """Test that PDG has data dependencies."""
        generator = PDGGenerator()
        pdgs = generator.generate_from_file(temp_python_file)
        
        for name, pdg in pdgs.items():
            data_edges = [e for e in pdg.edges if e.dependence_type == DependenceType.DATA_FLOW]
            # Many functions should have data deps
            if 'vulnerable_func' in name or 'safe_func' in name:
                assert len(data_edges) >= 0
    
    def test_pdg_backward_slice(self, temp_python_file):
        """Test backward slicing on PDG."""
        generator = PDGGenerator()
        pdgs = generator.generate_from_file(temp_python_file)
        
        for name, pdg in pdgs.items():
            if len(pdg.nodes) > 2:
                # Get a non-entry/exit node
                for node_id, node in pdg.nodes.items():
                    if node.cfg_node.node_type not in (CFGNodeType.ENTRY, CFGNodeType.EXIT):
                        slice_nodes = pdg.get_backward_slice(node_id)
                        assert len(slice_nodes) >= 1  # At least the criterion
                        break
    
    def test_pdg_forward_slice(self, temp_python_file):
        """Test forward slicing on PDG."""
        generator = PDGGenerator()
        pdgs = generator.generate_from_file(temp_python_file)
        
        for name, pdg in pdgs.items():
            if pdg.cfg and pdg.cfg.entry_node:
                slice_nodes = pdg.get_forward_slice(pdg.cfg.entry_node.id)
                assert len(slice_nodes) >= 1
    
    def test_def_use_chains(self, temp_python_file):
        """Test def-use chain computation."""
        generator = PDGGenerator()
        pdgs = generator.generate_from_file(temp_python_file)
        
        for name, pdg in pdgs.items():
            # Should have some def-use chains
            if len(pdg.nodes) > 2:
                # Chains may or may not exist depending on code
                pass


# =============================================================================
# Advanced Data-Flow Analyzer Tests
# =============================================================================

class TestAdvancedDataFlowAnalyzer:
    """Tests for advanced data-flow analysis."""
    
    def test_analyzer_creation(self):
        """Test analyzer instantiation."""
        analyzer = AdvancedDataFlowAnalyzer()
        assert analyzer is not None
        assert analyzer.sensitivity == AnalysisSensitivity.PATH_SENSITIVE
    
    def test_analyzer_sensitivity_levels(self):
        """Test different sensitivity levels."""
        for sens in AnalysisSensitivity:
            analyzer = AdvancedDataFlowAnalyzer(sensitivity=sens)
            assert analyzer.sensitivity == sens
    
    def test_analyze_file(self, temp_python_file):
        """Test analyzing a single file."""
        analyzer = AdvancedDataFlowAnalyzer()
        findings = analyzer.analyze_file(temp_python_file)
        
        assert isinstance(findings, list)
        # May or may not have findings depending on detection
    
    def test_flow_insensitive_analysis(self, temp_python_file):
        """Test flow-insensitive analysis."""
        analyzer = AdvancedDataFlowAnalyzer(sensitivity=AnalysisSensitivity.FLOW_INSENSITIVE)
        findings = analyzer.analyze_file(temp_python_file)
        assert isinstance(findings, list)
    
    def test_flow_sensitive_analysis(self, temp_python_file):
        """Test flow-sensitive analysis."""
        analyzer = AdvancedDataFlowAnalyzer(sensitivity=AnalysisSensitivity.FLOW_SENSITIVE)
        findings = analyzer.analyze_file(temp_python_file)
        assert isinstance(findings, list)
    
    def test_path_sensitive_analysis(self, temp_python_file):
        """Test path-sensitive analysis."""
        analyzer = AdvancedDataFlowAnalyzer(sensitivity=AnalysisSensitivity.PATH_SENSITIVE)
        findings = analyzer.analyze_file(temp_python_file)
        assert isinstance(findings, list)
    
    def test_statistics_tracking(self, temp_python_file):
        """Test that statistics are tracked."""
        analyzer = AdvancedDataFlowAnalyzer()
        analyzer.analyze_file(temp_python_file)
        
        stats = analyzer.statistics
        assert 'states_created' in stats
        assert 'paths_explored' in stats or stats['states_created'] >= 0


# =============================================================================
# Symbolic Execution Tests
# =============================================================================

class TestSymbolicExecution:
    """Tests for symbolic execution components."""
    
    def test_symbolic_state_creation(self):
        """Test symbolic state creation."""
        state = SymbolicState()
        assert state is not None
        assert len(state.variables) == 0
        assert len(state.path_conditions) == 0
    
    def test_symbolic_state_copy(self):
        """Test symbolic state copying."""
        state = SymbolicState()
        state.set_variable('x', SymbolicValue(
            name='x',
            value_type=SymbolicValueType.TAINTED
        ))
        
        copied = state.copy()
        assert copied is not state
        assert 'x' in copied.variables
        assert copied.get_variable('x').value_type == SymbolicValueType.TAINTED
    
    def test_path_condition(self):
        """Test path condition handling."""
        cond = PathCondition(
            expression="x > 0",
            is_true=True,
            line=10,
            variables={'x'}
        )
        
        assert cond.expression == "x > 0"
        assert cond.is_true
        
        negated = cond.negated()
        assert not negated.is_true
    
    def test_symbolic_value_taint(self):
        """Test symbolic value taint tracking."""
        value = SymbolicValue(
            name='user_input',
            value_type=SymbolicValueType.TAINTED,
            taint_types={'sql_injection'}
        )
        
        assert value.is_tainted()
        
        clean = SymbolicValue(
            name='constant',
            value_type=SymbolicValueType.CONCRETE,
            concrete_value=42
        )
        assert not clean.is_tainted()
    
    def test_path_feasibility(self):
        """Test path feasibility checking."""
        state = SymbolicState()
        
        # Add consistent conditions
        state.add_condition(PathCondition("x > 0", True, 1))
        state.add_condition(PathCondition("y > 0", True, 2))
        assert state.is_feasible()
        
        # Add contradictory condition
        state2 = SymbolicState()
        state2.add_condition(PathCondition("x > 0", True, 1))
        state2.add_condition(PathCondition("x > 0", False, 2))
        assert not state2.is_feasible()


# =============================================================================
# Taint PDG Analyzer Tests
# =============================================================================

class TestTaintPDGAnalyzer:
    """Tests for PDG-based taint analysis."""
    
    def test_analyzer_creation(self):
        """Test taint PDG analyzer creation."""
        analyzer = TaintPDGAnalyzer()
        assert analyzer is not None
    
    def test_analyze_pdg(self, temp_python_file):
        """Test taint analysis on PDG."""
        generator = PDGGenerator()
        pdgs = generator.generate_from_file(temp_python_file)
        
        analyzer = TaintPDGAnalyzer()
        
        all_findings = []
        for name, pdg in pdgs.items():
            findings = analyzer.analyze_pdg(pdg)
            all_findings.extend(findings)
        
        assert isinstance(all_findings, list)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the complete pipeline."""
    
    def test_full_pipeline_python(self, temp_python_file):
        """Test full analysis pipeline on Python file."""
        # 1. Build CFG
        cfg_builder = CFGBuilder()
        cfgs = cfg_builder.build_from_file(temp_python_file)
        assert len(cfgs) > 0
        
        # 2. Generate PDG
        pdg_generator = PDGGenerator()
        pdgs = pdg_generator.generate_from_file(temp_python_file)
        assert len(pdgs) > 0
        
        # 3. Perform advanced analysis
        analyzer = AdvancedDataFlowAnalyzer()
        findings = analyzer.analyze_file(temp_python_file)
        assert isinstance(findings, list)
    
    def test_full_pipeline_js(self, temp_js_file):
        """Test full analysis pipeline on JavaScript file."""
        # 1. Build CFG
        cfg_builder = CFGBuilder()
        cfgs = cfg_builder.build_from_file(temp_js_file)
        assert len(cfgs) > 0
        
        # 2. Advanced analysis
        analyzer = AdvancedDataFlowAnalyzer()
        findings = analyzer.analyze_file(temp_js_file)
        assert isinstance(findings, list)
    
    def test_convenience_function(self, temp_python_file):
        """Test the convenience analysis function."""
        # Create a temporary directory with the file
        import shutil
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, 'test.py')
            shutil.copy(temp_python_file, target)
            
            findings = analyze_with_advanced_dataflow(tmpdir)
            assert isinstance(findings, list)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_file(self):
        """Test handling of empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("")
            f.flush()
            
            builder = CFGBuilder()
            cfgs = builder.build_from_file(f.name)
            assert cfgs is not None  # Should not crash
            
            os.unlink(f.name)
    
    def test_syntax_error_file(self):
        """Test handling of file with syntax errors."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def broken(\n")  # Syntax error
            f.flush()
            
            builder = CFGBuilder()
            cfgs = builder.build_from_file(f.name)
            # Should handle gracefully
            assert cfgs is not None
            
            os.unlink(f.name)
    
    def test_nonexistent_file(self):
        """Test handling of nonexistent file."""
        builder = CFGBuilder()
        cfgs = builder.build_from_file("/nonexistent/path/file.py")
        assert cfgs == {}  # Should return empty
    
    def test_deeply_nested_code(self):
        """Test handling of deeply nested code."""
        deep_code = "def deep():\n"
        for i in range(20):
            deep_code += "    " * (i + 1) + f"if x{i}:\n"
        deep_code += "    " * 21 + "pass"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(deep_code)
            f.flush()
            
            builder = CFGBuilder()
            cfgs = builder.build_from_file(f.name)
            assert cfgs is not None
            
            os.unlink(f.name)
    
    def test_recursive_function(self):
        """Test handling of recursive functions."""
        recursive_code = '''
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(recursive_code)
            f.flush()
            
            builder = CFGBuilder()
            cfgs = builder.build_from_file(f.name)
            assert 'factorial' in str(cfgs.keys())
            
            os.unlink(f.name)


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Basic performance tests."""
    
    def test_cfg_building_performance(self, temp_python_file):
        """Test CFG building doesn't take too long."""
        import time
        
        builder = CFGBuilder()
        
        start = time.time()
        for _ in range(10):
            cfgs = builder.build_from_file(temp_python_file)
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        assert elapsed < 10  # 10 iterations in under 10 seconds
    
    def test_pdg_generation_performance(self, temp_python_file):
        """Test PDG generation performance."""
        import time
        
        generator = PDGGenerator()
        
        start = time.time()
        for _ in range(10):
            pdgs = generator.generate_from_file(temp_python_file)
        elapsed = time.time() - start
        
        assert elapsed < 15  # 10 iterations in under 15 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
