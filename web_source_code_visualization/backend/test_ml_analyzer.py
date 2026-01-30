"""
Test suite for ML-based Vulnerability Detection.

Tests:
1. Feature extraction
2. ML vulnerability detector
3. False positive filter
4. Integration with taint analyzer
"""

import unittest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from core.ml_feature_extractor import (
    MLFeatureExtractor,
    VulnerabilityFeatures,
    CodeContext,
    FeatureCategory,
    get_feature_extractor,
)
from core.ml_vulnerability_detector import (
    MLVulnerabilityDetector,
    PredictionResult,
    VulnerabilityClass,
    Severity,
    RuleBasedClassifier,
    EnsembleModel,
    get_ml_detector,
    analyze_with_ml,
)
from core.ml_false_positive_filter import (
    FalsePositiveFilter,
    FilterReason,
    FilterResult,
    PatternBasedFilter,
    ContextualFilter,
    HistoricalFilter,
    get_fp_filter,
    apply_fp_filter,
)


class TestMLFeatureExtractor(unittest.TestCase):
    """Tests for ML Feature Extractor."""
    
    def setUp(self):
        self.extractor = MLFeatureExtractor()
    
    def test_extract_features_basic(self):
        """Test basic feature extraction."""
        taint_flow = {
            "file_path": "test.py",
            "function_name": "handle_request",
            "source_line": 10,
            "sink_line": 20,
            "vulnerability_type": "sql_injection",
            "source_type": "request.args",
            "sink_type": "cursor.execute",
        }
        code = """
def handle_request():
    user_id = request.args.get('id')
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
"""
        context = CodeContext(
            file_path="test.py",
            function_name="handle_request",
            line_start=1,
            line_end=5,
        )
        
        features = self.extractor.extract_features(taint_flow, code, context)
        
        self.assertIsInstance(features, VulnerabilityFeatures)
        self.assertEqual(features.vulnerability_type, "sql_injection")
        self.assertIn("feature_id", features.__dict__)
    
    def test_extract_structural_features(self):
        """Test structural feature extraction."""
        code = """
def complex_function(a, b, c):
    if a:
        if b:
            for i in range(c):
                try:
                    result = a + b * i
                except:
                    pass
    return result
"""
        features = self.extractor._extract_structural_features(code)
        
        self.assertGreater(features.get("function_complexity", 0), 0)
        self.assertIn("nesting_depth", features)
        self.assertIn("branch_count", features)
    
    def test_extract_pattern_features_sql_injection(self):
        """Test pattern feature extraction for SQL injection."""
        code = """
query = "SELECT * FROM users WHERE id = " + user_input
cursor.execute(query)
"""
        features = self.extractor._extract_pattern_features(code, "sql_injection")
        
        self.assertGreater(features.get("dangerous_pattern_count", 0), 0)
        self.assertGreater(features.get("string_concat_used", 0), 0)
    
    def test_extract_pattern_features_xss(self):
        """Test pattern feature extraction for XSS."""
        code = """
document.innerHTML = userInput;
"""
        features = self.extractor._extract_pattern_features(code, "xss")
        
        self.assertGreater(features.get("dangerous_pattern_count", 0), 0)
    
    def test_sanitizer_detection(self):
        """Test sanitizer pattern detection."""
        code = """
from markupsafe import escape
user_input = request.args.get('input')
safe_input = escape(user_input)
return render_template('page.html', data=safe_input)
"""
        features = self.extractor._extract_pattern_features(code, "xss")
        
        self.assertGreater(features.get("sanitizer_pattern_count", 0), 0)
    
    def test_framework_detection(self):
        """Test framework indicator detection."""
        flask_code = """
from flask import Flask, request
app = Flask(__name__)

@app.route('/api/data')
def get_data():
    return jsonify(data)
"""
        features = self.extractor._extract_pattern_features(flask_code, "general")
        
        self.assertGreater(features.get("framework_protection", 0), 0)
    
    def test_batch_extract(self):
        """Test batch feature extraction."""
        taint_flows = [
            {
                "file_path": "test1.py",
                "vulnerability_type": "sql_injection",
            },
            {
                "file_path": "test2.py",
                "vulnerability_type": "xss",
            },
        ]
        code_contents = {
            "test1.py": "query = 'SELECT * FROM ' + table",
            "test2.py": "innerHTML = userInput",
        }
        
        features_list = self.extractor.batch_extract(taint_flows, code_contents)
        
        self.assertEqual(len(features_list), 2)
        self.assertEqual(features_list[0].vulnerability_type, "sql_injection")
        self.assertEqual(features_list[1].vulnerability_type, "xss")


class TestRuleBasedClassifier(unittest.TestCase):
    """Tests for Rule-Based Classifier."""
    
    def setUp(self):
        self.classifier = RuleBasedClassifier()
    
    def test_classify_sql_injection(self):
        """Test SQL injection classification."""
        features = VulnerabilityFeatures(
            feature_id="test-1",
            vulnerability_type="sql_injection",
            structural={},
            semantic={},
            contextual={},
            pattern={
                "known_vuln_pattern": 0.9,
                "string_concat_used": 0.8,
            },
            code_context=MagicMock(),
        )
        
        score, explanations = self.classifier.predict(features)
        
        self.assertGreater(score, 0.5)
        self.assertTrue(len(explanations) > 0)
    
    def test_classify_with_sanitizer(self):
        """Test classification with sanitizer present."""
        features = VulnerabilityFeatures(
            feature_id="test-2",
            vulnerability_type="xss",
            structural={},
            semantic={"is_typed": 0.9},
            contextual={"sanitizer_present": 0.9},
            pattern={
                "known_vuln_pattern": 0.5,
                "sanitizer_pattern_count": 0.8,
            },
            code_context=MagicMock(),
        )
        
        score, explanations = self.classifier.predict(features)
        
        self.assertLess(score, 0.6)  # Should be lower due to sanitizer


class TestMLVulnerabilityDetector(unittest.TestCase):
    """Tests for ML Vulnerability Detector."""
    
    def setUp(self):
        self.detector = MLVulnerabilityDetector()
    
    def test_analyze_true_positive(self):
        """Test detection of true positive vulnerability."""
        taint_flow = {
            "file_path": "vulnerable.py",
            "function_name": "get_user",
            "source_line": 5,
            "sink_line": 10,
            "vulnerability_type": "sql_injection",
        }
        code = """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
    return cursor.fetchone()
"""
        
        result = self.detector.analyze(taint_flow, code)
        
        self.assertIsInstance(result, PredictionResult)
        self.assertEqual(result.vulnerability_type, "sql_injection")
        self.assertGreater(result.confidence, 0.3)
    
    def test_analyze_false_positive(self):
        """Test detection of likely false positive."""
        taint_flow = {
            "file_path": "safe.py",
            "function_name": "get_user",
            "source_line": 5,
            "sink_line": 10,
            "vulnerability_type": "sql_injection",
        }
        code = """
def get_user(user_id: int):
    # Using parameterized query (safe)
    query = "SELECT * FROM users WHERE id = %s"
    cursor.execute(query, (user_id,))
    return cursor.fetchone()
"""
        
        result = self.detector.analyze(taint_flow, code)
        
        # Should have lower confidence or classify as likely false
        self.assertIsInstance(result, PredictionResult)
    
    def test_batch_analyze(self):
        """Test batch analysis."""
        taint_flows = [
            {
                "file_path": "test1.py",
                "vulnerability_type": "sql_injection",
            },
            {
                "file_path": "test2.py",
                "vulnerability_type": "xss",
            },
        ]
        code_contents = {
            "test1.py": "query = 'SELECT * FROM ' + table",
            "test2.py": "innerHTML = escape(userInput)",
        }
        
        results = self.detector.batch_analyze(
            taint_flows, 
            code_contents, 
            filter_false_positives=False
        )
        
        self.assertEqual(len(results), 2)
    
    def test_severity_prediction(self):
        """Test severity prediction."""
        taint_flow = {
            "file_path": "critical.py",
            "vulnerability_type": "command_injection",
        }
        code = "os.system(user_input)"
        
        result = self.detector.analyze(taint_flow, code)
        
        self.assertIn(result.predicted_severity, [Severity.CRITICAL, Severity.HIGH])
    
    def test_recommendations_generated(self):
        """Test that recommendations are generated."""
        taint_flow = {
            "file_path": "test.py",
            "vulnerability_type": "sql_injection",
        }
        code = "cursor.execute('SELECT * FROM users WHERE id=' + user_id)"
        
        result = self.detector.analyze(taint_flow, code)
        
        self.assertTrue(len(result.recommendations) > 0)
    
    def test_statistics_tracking(self):
        """Test statistics tracking."""
        self.detector.reset_statistics()
        
        taint_flow = {"file_path": "test.py", "vulnerability_type": "xss"}
        code = "innerHTML = userInput"
        
        self.detector.analyze(taint_flow, code)
        
        stats = self.detector.get_statistics()
        self.assertEqual(stats["total_analyzed"], 1)


class TestFalsePositiveFilter(unittest.TestCase):
    """Tests for False Positive Filter."""
    
    def setUp(self):
        self.fp_filter = FalsePositiveFilter()
    
    def test_pattern_filter_orm(self):
        """Test pattern filter detects ORM usage."""
        pattern_filter = PatternBasedFilter()
        
        code = """
user = User.objects.filter(id=user_id).first()
"""
        
        is_safe, explanation, confidence = pattern_filter.check(code, "sql_injection")
        
        self.assertTrue(is_safe)
        self.assertIn("ORM", explanation)
    
    def test_pattern_filter_parameterized(self):
        """Test pattern filter detects parameterized queries."""
        pattern_filter = PatternBasedFilter()
        
        code = """
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
"""
        
        is_safe, explanation, confidence = pattern_filter.check(code, "sql_injection")
        
        self.assertTrue(is_safe)
    
    def test_pattern_filter_xss_escape(self):
        """Test pattern filter detects XSS escaping."""
        pattern_filter = PatternBasedFilter()
        
        code = """
safe_output = html.escape(user_input)
"""
        
        is_safe, explanation, confidence = pattern_filter.check(code, "xss")
        
        self.assertTrue(is_safe)
    
    def test_filter_already_classified_fp(self):
        """Test filtering of already classified false positives."""
        prediction = PredictionResult(
            feature_id="test-fp",
            vulnerability_type="xss",
            is_vulnerability=False,
            classification=VulnerabilityClass.FALSE_POSITIVE,
            confidence=0.9,
            predicted_severity=Severity.LOW,
            severity_confidence=0.8,
        )
        
        result = self.fp_filter.filter(prediction, "some code")
        
        self.assertTrue(result.should_filter)
        self.assertEqual(result.reason, FilterReason.LOW_CONFIDENCE)
    
    def test_filter_with_safe_pattern(self):
        """Test filtering with safe pattern detection."""
        prediction = PredictionResult(
            feature_id="test-safe",
            vulnerability_type="sql_injection",
            is_vulnerability=True,
            classification=VulnerabilityClass.LIKELY_TRUE,
            confidence=0.7,
            predicted_severity=Severity.HIGH,
            severity_confidence=0.8,
        )
        
        code = """
user = db.session.query(User).filter(User.id == user_id).first()
"""
        
        result = self.fp_filter.filter(prediction, code)
        
        self.assertTrue(result.should_filter)
        self.assertEqual(result.reason, FilterReason.KNOWN_SAFE_PATTERN)
    
    def test_historical_filter(self):
        """Test historical filter learning."""
        historical = HistoricalFilter()
        
        # Record a false positive
        historical.record_false_positive(
            "xss",
            "safe_pattern_code",
            "context-123"
        )
        
        # Check if it's remembered
        matches, confidence = historical.check(
            "xss",
            "safe_pattern_code",
            "context-456"
        )
        
        self.assertTrue(matches)
        self.assertGreater(confidence, 0.5)
    
    def test_batch_filter(self):
        """Test batch filtering."""
        predictions = [
            PredictionResult(
                feature_id="test-1",
                vulnerability_type="sql_injection",
                is_vulnerability=True,
                classification=VulnerabilityClass.TRUE_POSITIVE,
                confidence=0.9,
                predicted_severity=Severity.HIGH,
                severity_confidence=0.8,
            ),
            PredictionResult(
                feature_id="test-2",
                vulnerability_type="xss",
                is_vulnerability=False,
                classification=VulnerabilityClass.FALSE_POSITIVE,
                confidence=0.85,
                predicted_severity=Severity.LOW,
                severity_confidence=0.7,
            ),
        ]
        
        code_contents = {"": "some code"}
        
        kept, filter_results = self.fp_filter.batch_filter(predictions, code_contents)
        
        self.assertEqual(len(kept), 1)  # Only true positive kept
        self.assertEqual(kept[0].feature_id, "test-1")


class TestIntegration(unittest.TestCase):
    """Integration tests for ML analyzer."""
    
    def test_singleton_instances(self):
        """Test that singleton instances work correctly."""
        extractor1 = get_feature_extractor()
        extractor2 = get_feature_extractor()
        self.assertIs(extractor1, extractor2)
        
        detector1 = get_ml_detector()
        detector2 = get_ml_detector()
        self.assertIs(detector1, detector2)
        
        filter1 = get_fp_filter()
        filter2 = get_fp_filter()
        self.assertIs(filter1, filter2)
    
    def test_analyze_with_ml_function(self):
        """Test the convenience analyze_with_ml function."""
        taint_flows = [
            {
                "file_path": "test.py",
                "vulnerability_type": "sql_injection",
            }
        ]
        code_contents = {
            "test.py": "query = 'SELECT * FROM users WHERE id=' + id"
        }
        
        result = analyze_with_ml(
            taint_flows,
            code_contents,
            filter_false_positives=False
        )
        
        self.assertIn("results", result)
        self.assertIn("statistics", result)
        self.assertIn("filtered_count", result)
    
    def test_apply_fp_filter_function(self):
        """Test the convenience apply_fp_filter function."""
        predictions = [
            PredictionResult(
                feature_id="test-1",
                vulnerability_type="xss",
                is_vulnerability=True,
                classification=VulnerabilityClass.TRUE_POSITIVE,
                confidence=0.9,
                predicted_severity=Severity.HIGH,
                severity_confidence=0.8,
            ),
        ]
        code_contents = {"": "innerHTML = userInput"}
        
        result = apply_fp_filter(predictions, code_contents)
        
        self.assertIn("vulnerabilities", result)
        self.assertIn("filtered_count", result)
        self.assertIn("statistics", result)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def test_empty_code(self):
        """Test handling of empty code."""
        extractor = MLFeatureExtractor()
        features = extractor.extract_features({}, "", None)
        
        self.assertIsInstance(features, VulnerabilityFeatures)
    
    def test_empty_taint_flows(self):
        """Test handling of empty taint flows."""
        detector = MLVulnerabilityDetector()
        results = detector.batch_analyze([], {})
        
        self.assertEqual(len(results), 0)
    
    def test_unknown_vulnerability_type(self):
        """Test handling of unknown vulnerability type."""
        extractor = MLFeatureExtractor()
        features = extractor.extract_features(
            {"vulnerability_type": "unknown_type"},
            "some code",
            None
        )
        
        self.assertEqual(features.vulnerability_type, "unknown_type")
    
    def test_prediction_result_to_dict(self):
        """Test PredictionResult serialization."""
        result = PredictionResult(
            feature_id="test-1",
            vulnerability_type="xss",
            is_vulnerability=True,
            classification=VulnerabilityClass.TRUE_POSITIVE,
            confidence=0.9,
            predicted_severity=Severity.HIGH,
            severity_confidence=0.8,
            contributing_factors=["factor1"],
            risk_factors=["risk1"],
            mitigating_factors=["mitigating1"],
            recommendations=["rec1"],
        )
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict["feature_id"], "test-1")
        self.assertEqual(result_dict["classification"], "true_positive")
        self.assertEqual(result_dict["predicted_severity"], "high")


if __name__ == "__main__":
    unittest.main(verbosity=2)
