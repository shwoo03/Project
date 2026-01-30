"""
ML-based False Positive Filter.

This module provides specialized filtering for reducing false positives
in vulnerability detection using:
1. Pattern-based rules
2. Context analysis
3. Historical learning
4. Framework-specific heuristics
"""

from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import logging
from collections import defaultdict

from .ml_feature_extractor import VulnerabilityFeatures, FeatureCategory
from .ml_vulnerability_detector import (
    PredictionResult, VulnerabilityClass, Severity
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FilterReason(Enum):
    """Reason for filtering a vulnerability."""
    SANITIZED = "sanitized"
    FRAMEWORK_PROTECTED = "framework_protected"
    TYPE_SAFE = "type_safe"
    VALIDATION_PRESENT = "validation_present"
    KNOWN_SAFE_PATTERN = "known_safe_pattern"
    CONTEXT_INDICATES_SAFE = "context_indicates_safe"
    LOW_CONFIDENCE = "low_confidence"
    HISTORICAL_FP = "historical_false_positive"


@dataclass
class FilterResult:
    """Result of false positive filtering."""
    should_filter: bool
    reason: Optional[FilterReason] = None
    confidence: float = 0.0
    explanation: str = ""
    original_prediction: Optional[PredictionResult] = None


class PatternBasedFilter:
    """
    Pattern-based false positive filter.
    Uses regex and AST patterns to identify safe code.
    """
    
    # Safe patterns by vulnerability type
    SAFE_PATTERNS = {
        "sql_injection": [
            # ORM usage
            (r'\.filter\s*\(', "ORM filter method usage"),
            (r'\.objects\.', "Django ORM usage"),
            (r'db\.session\.query', "SQLAlchemy session query"),
            (r'\.where\s*\([^+]*\)', "WHERE clause without concatenation"),
            # Parameterized queries
            (r'\?\s*,|\%s\s*,|\$\d+', "Parameterized query placeholder"),
            (r'cursor\.execute\s*\([^,]+,\s*[\[\(]', "Parameterized execute"),
        ],
        "xss": [
            # Template auto-escaping
            (r'\{\{\s*\w+\s*\}\}', "Jinja2/Django template (auto-escaped)"),
            (r'<%-.*?%>', "EJS escaped output"),
            (r'v-text=', "Vue.js v-text (auto-escaped)"),
            # Encoding functions
            (r'html\.escape\(', "HTML escape function"),
            (r'htmlentities\(', "PHP htmlentities"),
            (r'encodeURIComponent\(', "URL encoding"),
            (r'DOMPurify\.sanitize\(', "DOMPurify sanitization"),
        ],
        "command_injection": [
            # Safe execution patterns
            (r'subprocess\.run\([^,]+,\s*shell\s*=\s*False', "subprocess with shell=False"),
            (r'shlex\.quote\(', "Shell quoting"),
            (r'escapeshellarg\(', "PHP shell escape"),
            (r'ProcessBuilder', "Java ProcessBuilder (safer)"),
        ],
        "path_traversal": [
            # Path validation
            (r'os\.path\.basename\(', "Basename extraction"),
            (r'\.resolve\(\)', "Path resolution"),
            (r'realpath\(', "Real path resolution"),
            (r'startswith\(["\']/', "Path prefix check"),
            (r'Path\([^)]+\)\.is_relative_to\(', "Python path containment check"),
        ],
        "ssrf": [
            # URL validation
            (r'urlparse\([^)]+\)\.netloc\s*(==|in)', "URL host validation"),
            (r'allowed_hosts\s*=|ALLOWED_HOSTS', "Host whitelist"),
            (r'\.startswith\s*\(["\']https?://', "Protocol check"),
        ],
    }
    
    # Universal safe patterns
    UNIVERSAL_SAFE_PATTERNS = [
        (r'# nosec|# noqa.*security|#\s*safe', "Security annotation"),
        (r'@safe|@sanitized|@validated', "Safety decorator"),
        (r'if\s+not\s+\w+:\s*return|if\s+not\s+\w+:\s*raise', "Early validation return"),
    ]
    
    def check(
        self, 
        code: str, 
        vuln_type: str
    ) -> Tuple[bool, Optional[str], float]:
        """
        Check if code matches safe patterns.
        
        Returns:
            Tuple of (is_safe, explanation, confidence)
        """
        normalized_type = vuln_type.lower().replace("-", "_").replace(" ", "_")
        
        # Check type-specific patterns
        patterns = self.SAFE_PATTERNS.get(normalized_type, [])
        for pattern, explanation in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True, explanation, 0.8
        
        # Check universal patterns
        for pattern, explanation in self.UNIVERSAL_SAFE_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return True, explanation, 0.9
        
        return False, None, 0.0


class ContextualFilter:
    """
    Contextual false positive filter.
    Analyzes the surrounding code context.
    """
    
    # Framework-specific safe contexts
    FRAMEWORK_CONTEXTS = {
        "django": {
            "patterns": [
                r'from django',
                r'django\.db\.models',
            ],
            "safe_indicators": [
                "Model field access (Django ORM protects against SQLi)",
                "Django template (auto-escaping enabled by default)",
            ],
        },
        "flask": {
            "patterns": [
                r'from flask',
                r'Flask\(',
            ],
            "safe_indicators": [
                "Jinja2 auto-escaping",
                "SQLAlchemy ORM",
            ],
        },
        "spring": {
            "patterns": [
                r'@(Controller|RestController|Service)',
                r'import org\.springframework',
            ],
            "safe_indicators": [
                "Spring Security CSRF protection",
                "JPA/Hibernate ORM",
            ],
        },
        "express": {
            "patterns": [
                r'express\(\)',
                r'require\(["\']express["\']\)',
            ],
            "safe_indicators": [
                "Helmet.js security headers",
                "Express validator middleware",
            ],
        },
    }
    
    def analyze(
        self,
        features: VulnerabilityFeatures,
        code: str
    ) -> Tuple[bool, List[str]]:
        """
        Analyze contextual safety.
        
        Returns:
            Tuple of (is_safe, reasons)
        """
        safety_reasons = []
        
        # Check framework context
        for framework, config in self.FRAMEWORK_CONTEXTS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, code):
                    # Framework detected, check for safe indicators
                    safety_reasons.extend(config["safe_indicators"])
                    break
        
        # Check feature-based safety
        if features.contextual.get("sanitizer_present", 0) > 0.7:
            safety_reasons.append("Strong sanitization detected")
        
        if features.semantic.get("is_typed", 0) > 0.7:
            safety_reasons.append("Strong typing provides protection")
        
        if features.pattern.get("framework_protection", 0) > 0.7:
            safety_reasons.append("Framework security features active")
        
        is_safe = len(safety_reasons) >= 2  # Multiple safety indicators
        return is_safe, safety_reasons


class HistoricalFilter:
    """
    Historical false positive filter.
    Learns from past false positives.
    """
    
    def __init__(self):
        self.fp_patterns: Dict[str, Set[str]] = defaultdict(set)
        self.fp_contexts: Dict[str, Set[str]] = defaultdict(set)
        self.history: List[Dict[str, Any]] = []
    
    def record_false_positive(
        self,
        vuln_type: str,
        code_snippet: str,
        context_signature: str
    ):
        """Record a confirmed false positive for learning."""
        self.fp_patterns[vuln_type].add(code_snippet[:100])
        self.fp_contexts[vuln_type].add(context_signature)
        self.history.append({
            "type": vuln_type,
            "snippet": code_snippet[:100],
            "context": context_signature,
        })
    
    def check(
        self,
        vuln_type: str,
        code_snippet: str,
        context_signature: str
    ) -> Tuple[bool, float]:
        """
        Check if similar patterns were marked as false positive.
        
        Returns:
            Tuple of (matches_history, confidence)
        """
        normalized_type = vuln_type.lower()
        
        # Check exact pattern match
        if code_snippet[:100] in self.fp_patterns.get(normalized_type, set()):
            return True, 0.95
        
        # Check context match
        if context_signature in self.fp_contexts.get(normalized_type, set()):
            return True, 0.75
        
        return False, 0.0


class FalsePositiveFilter:
    """
    Main false positive filter combining multiple strategies.
    """
    
    def __init__(self):
        self.pattern_filter = PatternBasedFilter()
        self.contextual_filter = ContextualFilter()
        self.historical_filter = HistoricalFilter()
        
        # Filter statistics
        self.stats = {
            "total_checked": 0,
            "filtered": 0,
            "by_reason": defaultdict(int),
        }
    
    def filter(
        self,
        prediction: PredictionResult,
        code: str,
        context_signature: Optional[str] = None
    ) -> FilterResult:
        """
        Apply false positive filtering to a prediction.
        
        Args:
            prediction: The original prediction result
            code: The relevant code snippet
            context_signature: Optional context identifier for historical matching
            
        Returns:
            FilterResult indicating whether to filter
        """
        self.stats["total_checked"] += 1
        
        # Already classified as false positive by ML
        if prediction.classification in [
            VulnerabilityClass.FALSE_POSITIVE,
            VulnerabilityClass.LIKELY_FALSE
        ]:
            self._update_stats(FilterReason.LOW_CONFIDENCE)
            return FilterResult(
                should_filter=True,
                reason=FilterReason.LOW_CONFIDENCE,
                confidence=prediction.confidence,
                explanation="ML model classified as likely false positive",
                original_prediction=prediction,
            )
        
        # Pattern-based check
        is_safe, explanation, confidence = self.pattern_filter.check(
            code, prediction.vulnerability_type
        )
        if is_safe:
            self._update_stats(FilterReason.KNOWN_SAFE_PATTERN)
            return FilterResult(
                should_filter=True,
                reason=FilterReason.KNOWN_SAFE_PATTERN,
                confidence=confidence,
                explanation=explanation or "Safe pattern detected",
                original_prediction=prediction,
            )
        
        # Contextual check
        if prediction.features:
            is_safe, reasons = self.contextual_filter.analyze(
                prediction.features, code
            )
            if is_safe:
                self._update_stats(FilterReason.CONTEXT_INDICATES_SAFE)
                return FilterResult(
                    should_filter=True,
                    reason=FilterReason.CONTEXT_INDICATES_SAFE,
                    confidence=0.75,
                    explanation="; ".join(reasons[:3]),
                    original_prediction=prediction,
                )
        
        # Historical check
        if context_signature:
            matches, confidence = self.historical_filter.check(
                prediction.vulnerability_type,
                code,
                context_signature
            )
            if matches:
                self._update_stats(FilterReason.HISTORICAL_FP)
                return FilterResult(
                    should_filter=True,
                    reason=FilterReason.HISTORICAL_FP,
                    confidence=confidence,
                    explanation="Similar pattern was previously marked as false positive",
                    original_prediction=prediction,
                )
        
        # Feature-based checks
        if prediction.features:
            features = prediction.features
            
            # Check sanitization
            if features.contextual.get("sanitizer_present", 0) > 0.8:
                self._update_stats(FilterReason.SANITIZED)
                return FilterResult(
                    should_filter=True,
                    reason=FilterReason.SANITIZED,
                    confidence=0.85,
                    explanation="Strong sanitization detected in data flow",
                    original_prediction=prediction,
                )
            
            # Check validation
            if features.pattern.get("validated_input", 0) > 0.8:
                self._update_stats(FilterReason.VALIDATION_PRESENT)
                return FilterResult(
                    should_filter=True,
                    reason=FilterReason.VALIDATION_PRESENT,
                    confidence=0.8,
                    explanation="Input validation detected",
                    original_prediction=prediction,
                )
            
            # Check type safety
            if features.semantic.get("is_typed", 0) > 0.9:
                self._update_stats(FilterReason.TYPE_SAFE)
                return FilterResult(
                    should_filter=True,
                    reason=FilterReason.TYPE_SAFE,
                    confidence=0.7,
                    explanation="Strong type safety provides protection",
                    original_prediction=prediction,
                )
        
        # Not filtered
        return FilterResult(
            should_filter=False,
            original_prediction=prediction,
        )
    
    def batch_filter(
        self,
        predictions: List[PredictionResult],
        code_contents: Dict[str, str]
    ) -> Tuple[List[PredictionResult], List[FilterResult]]:
        """
        Apply filtering to multiple predictions.
        
        Returns:
            Tuple of (kept_predictions, filter_results)
        """
        kept = []
        filter_results = []
        
        for pred in predictions:
            file_path = ""
            if pred.features:
                file_path = getattr(pred.features.code_context, 'file_path', '')
            code = code_contents.get(file_path, "")
            
            result = self.filter(pred, code)
            filter_results.append(result)
            
            if not result.should_filter:
                kept.append(pred)
        
        return kept, filter_results
    
    def record_feedback(
        self,
        prediction: PredictionResult,
        is_true_positive: bool,
        code: str,
        context_signature: Optional[str] = None
    ):
        """Record user feedback for learning."""
        if not is_true_positive:
            self.historical_filter.record_false_positive(
                prediction.vulnerability_type,
                code,
                context_signature or f"{prediction.feature_id}"
            )
    
    def _update_stats(self, reason: FilterReason):
        """Update filter statistics."""
        self.stats["filtered"] += 1
        self.stats["by_reason"][reason.value] += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get filtering statistics."""
        total = self.stats["total_checked"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "filter_rate": round(self.stats["filtered"] / total * 100, 2),
        }


# Singleton instance
_fp_filter: Optional[FalsePositiveFilter] = None

def get_fp_filter() -> FalsePositiveFilter:
    """Get singleton FalsePositiveFilter instance."""
    global _fp_filter
    if _fp_filter is None:
        _fp_filter = FalsePositiveFilter()
    return _fp_filter


def apply_fp_filter(
    predictions: List[PredictionResult],
    code_contents: Dict[str, str]
) -> Dict[str, Any]:
    """
    Convenience function to apply false positive filtering.
    
    Args:
        predictions: List of prediction results
        code_contents: Map of file paths to code content
        
    Returns:
        Dict with filtered results and statistics
    """
    fp_filter = get_fp_filter()
    kept, filter_results = fp_filter.batch_filter(predictions, code_contents)
    
    return {
        "vulnerabilities": [p.to_dict() for p in kept],
        "filtered_count": len(predictions) - len(kept),
        "filter_reasons": [
            {
                "id": fr.original_prediction.feature_id if fr.original_prediction else "",
                "reason": fr.reason.value if fr.reason else None,
                "explanation": fr.explanation,
            }
            for fr in filter_results if fr.should_filter
        ],
        "statistics": fp_filter.get_statistics(),
    }
