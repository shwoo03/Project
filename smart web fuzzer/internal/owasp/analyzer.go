// Package owasp provides response analysis for vulnerability detection.
package owasp

import (
	"regexp"
	"strings"
)

// ResponseAnalyzer analyzes HTTP responses for vulnerability indicators
type ResponseAnalyzer struct {
	patterns map[VulnerabilityType][]*regexp.Regexp
}

// NewResponseAnalyzer creates a new response analyzer
func NewResponseAnalyzer() *ResponseAnalyzer {
	ra := &ResponseAnalyzer{
		patterns: make(map[VulnerabilityType][]*regexp.Regexp),
	}
	ra.initPatterns()
	return ra
}

// initPatterns initializes detection patterns
func (ra *ResponseAnalyzer) initPatterns() {
	// SQL Injection patterns
	ra.patterns[SQLInjection] = []*regexp.Regexp{
		regexp.MustCompile(`(?i)sql\s*syntax`),
		regexp.MustCompile(`(?i)mysql.*error`),
		regexp.MustCompile(`(?i)postgresql.*error`),
		regexp.MustCompile(`(?i)sqlite.*error`),
		regexp.MustCompile(`(?i)oracle.*error`),
		regexp.MustCompile(`(?i)ORA-\d{5}`),
		regexp.MustCompile(`(?i)quoted string not properly terminated`),
		regexp.MustCompile(`(?i)unclosed quotation`),
		regexp.MustCompile(`(?i)SQLSTATE\[`),
		regexp.MustCompile(`(?i)Warning:.*mysql_`),
		regexp.MustCompile(`(?i)Warning:.*pg_`),
		regexp.MustCompile(`(?i)Microsoft SQL Server`),
		regexp.MustCompile(`(?i)ODBC.*Driver`),
	}

	// XSS patterns (reflected input)
	ra.patterns[XSS] = []*regexp.Regexp{
		regexp.MustCompile(`<script[^>]*>.*?</script>`),
		regexp.MustCompile(`on\w+\s*=\s*['"]*[^'"]*['"]`),
		regexp.MustCompile(`javascript:`),
		regexp.MustCompile(`<img[^>]+onerror\s*=`),
		regexp.MustCompile(`<svg[^>]+onload\s*=`),
	}

	// Command Injection patterns
	ra.patterns[OSCommand] = []*regexp.Regexp{
		regexp.MustCompile(`uid=\d+\(.*?\)\s+gid=\d+`),
		regexp.MustCompile(`root:.*:0:0:`),
		regexp.MustCompile(`\[boot loader\]`),
		regexp.MustCompile(`(?i)volume\s+serial\s+number`),
		regexp.MustCompile(`(?i)directory\s+of\s+`),
	}

	// Path Traversal patterns
	ra.patterns[BrokenAccessControl] = []*regexp.Regexp{
		regexp.MustCompile(`root:x:0:0:`),
		regexp.MustCompile(`\[fonts\]`),
		regexp.MustCompile(`\[extensions\]`),
		regexp.MustCompile(`(?i)warning:.*include\(`),
		regexp.MustCompile(`(?i)failed to open stream`),
	}

	// XXE patterns
	ra.patterns[XXE] = []*regexp.Regexp{
		regexp.MustCompile(`root:.*:0:0:`),
		regexp.MustCompile(`(?i)external entity`),
		regexp.MustCompile(`(?i)entity.*not defined`),
		regexp.MustCompile(`SYSTEM.*file:`),
	}

	// SSRF patterns
	ra.patterns[SSRF] = []*regexp.Regexp{
		regexp.MustCompile(`(?i)ami-[a-z0-9]+`),
		regexp.MustCompile(`(?i)instance-id`),
		regexp.MustCompile(`169\.254\.169\.254`),
		regexp.MustCompile(`(?i)internal\s+server`),
	}

	// Information Disclosure patterns
	ra.patterns[SensitiveDataExposure] = []*regexp.Regexp{
		regexp.MustCompile(`(?i)password\s*[:=]`),
		regexp.MustCompile(`(?i)api[_-]?key\s*[:=]`),
		regexp.MustCompile(`(?i)secret[_-]?key\s*[:=]`),
		regexp.MustCompile(`(?i)private[_-]?key`),
		regexp.MustCompile(`(?i)access[_-]?token`),
		regexp.MustCompile(`(?i)aws[_-]?secret`),
		regexp.MustCompile(`-----BEGIN.*PRIVATE KEY-----`),
		regexp.MustCompile(`(?i)jdbc:.*://`),
		regexp.MustCompile(`(?i)mongodb://.*@`),
	}

	// Stack Trace / Error patterns
	ra.patterns[VerboseErrors] = []*regexp.Regexp{
		regexp.MustCompile(`(?i)stack\s*trace`),
		regexp.MustCompile(`(?i)at\s+\w+\.\w+\(.*:\d+\)`),
		regexp.MustCompile(`(?i)exception\s+in\s+thread`),
		regexp.MustCompile(`(?i)traceback\s+\(most recent`),
		regexp.MustCompile(`(?i)Parse\s+error:`),
		regexp.MustCompile(`(?i)Fatal\s+error:`),
		regexp.MustCompile(`(?i)undefined\s+index`),
	}
}

// Analyze analyzes a response for vulnerabilities
func (ra *ResponseAnalyzer) Analyze(body []byte, vulnType VulnerabilityType) []AnalysisResult {
	var results []AnalysisResult
	bodyStr := string(body)

	patterns, ok := ra.patterns[vulnType]
	if !ok {
		return results
	}

	for _, pattern := range patterns {
		matches := pattern.FindAllString(bodyStr, -1)
		for _, match := range matches {
			results = append(results, AnalysisResult{
				Type:     vulnType,
				Pattern:  pattern.String(),
				Match:    match,
				Position: strings.Index(bodyStr, match),
			})
		}
	}

	return results
}

// AnalyzeAll analyzes a response for all vulnerability types
func (ra *ResponseAnalyzer) AnalyzeAll(body []byte) []AnalysisResult {
	var results []AnalysisResult

	for vulnType := range ra.patterns {
		typeResults := ra.Analyze(body, vulnType)
		results = append(results, typeResults...)
	}

	return results
}

// AnalysisResult represents an analysis finding
type AnalysisResult struct {
	Type     VulnerabilityType
	Pattern  string
	Match    string
	Position int
}

// HeaderAnalyzer analyzes HTTP headers for security issues
type HeaderAnalyzer struct{}

// NewHeaderAnalyzer creates a new header analyzer
func NewHeaderAnalyzer() *HeaderAnalyzer {
	return &HeaderAnalyzer{}
}

// SecurityHeader represents a security header check
type SecurityHeader struct {
	Name        string
	Required    bool
	Recommended string
	Severity    Severity
	CWE         string
}

// RequiredSecurityHeaders defines expected security headers
var RequiredSecurityHeaders = []SecurityHeader{
	{Name: "Strict-Transport-Security", Required: true, Recommended: "max-age=31536000; includeSubDomains", Severity: Medium, CWE: "CWE-319"},
	{Name: "X-Content-Type-Options", Required: true, Recommended: "nosniff", Severity: Low, CWE: "CWE-16"},
	{Name: "X-Frame-Options", Required: true, Recommended: "DENY", Severity: Medium, CWE: "CWE-1021"},
	{Name: "X-XSS-Protection", Required: false, Recommended: "1; mode=block", Severity: Low, CWE: "CWE-79"},
	{Name: "Content-Security-Policy", Required: true, Recommended: "default-src 'self'", Severity: Medium, CWE: "CWE-79"},
	{Name: "Referrer-Policy", Required: false, Recommended: "strict-origin-when-cross-origin", Severity: Low, CWE: "CWE-200"},
	{Name: "Permissions-Policy", Required: false, Recommended: "geolocation=(), microphone=()", Severity: Low, CWE: "CWE-16"},
}

// AnalyzeHeaders analyzes response headers
func (ha *HeaderAnalyzer) AnalyzeHeaders(headers map[string]string) []HeaderFinding {
	var findings []HeaderFinding

	// Check for missing security headers
	for _, required := range RequiredSecurityHeaders {
		value, exists := headers[required.Name]
		if !exists {
			findings = append(findings, HeaderFinding{
				Header:      required.Name,
				Issue:       "Missing security header",
				Severity:    required.Severity,
				Recommended: required.Recommended,
				CWE:         required.CWE,
			})
		} else if required.Required && value == "" {
			findings = append(findings, HeaderFinding{
				Header:      required.Name,
				Issue:       "Empty security header",
				Severity:    required.Severity,
				Recommended: required.Recommended,
				CWE:         required.CWE,
			})
		}
	}

	// Check for insecure headers
	if server, ok := headers["Server"]; ok && server != "" {
		findings = append(findings, HeaderFinding{
			Header:      "Server",
			Issue:       "Server version disclosed: " + server,
			Severity:    Low,
			Recommended: "Remove or obfuscate Server header",
			CWE:         "CWE-200",
		})
	}

	if powered, ok := headers["X-Powered-By"]; ok && powered != "" {
		findings = append(findings, HeaderFinding{
			Header:      "X-Powered-By",
			Issue:       "Technology stack disclosed: " + powered,
			Severity:    Low,
			Recommended: "Remove X-Powered-By header",
			CWE:         "CWE-200",
		})
	}

	return findings
}

// HeaderFinding represents a header security finding
type HeaderFinding struct {
	Header      string
	Issue       string
	Severity    Severity
	Recommended string
	CWE         string
}

// TimingAnalyzer detects timing-based vulnerabilities
type TimingAnalyzer struct {
	baselineMs int64
	threshold  float64
}

// NewTimingAnalyzer creates a new timing analyzer
func NewTimingAnalyzer(baselineMs int64) *TimingAnalyzer {
	return &TimingAnalyzer{
		baselineMs: baselineMs,
		threshold:  2.0, // 2x baseline is suspicious
	}
}

// Analyze checks if response time indicates a vulnerability
func (ta *TimingAnalyzer) Analyze(responseTimeMs int64) *TimingResult {
	if ta.baselineMs == 0 {
		return nil
	}

	ratio := float64(responseTimeMs) / float64(ta.baselineMs)

	if ratio >= ta.threshold {
		return &TimingResult{
			BaselineMs:   ta.baselineMs,
			ResponseMs:   responseTimeMs,
			Ratio:        ratio,
			IsSuspicious: true,
		}
	}

	return &TimingResult{
		BaselineMs:   ta.baselineMs,
		ResponseMs:   responseTimeMs,
		Ratio:        ratio,
		IsSuspicious: false,
	}
}

// TimingResult represents timing analysis result
type TimingResult struct {
	BaselineMs   int64
	ResponseMs   int64
	Ratio        float64
	IsSuspicious bool
}

// DifferentialAnalyzer compares responses for differences
type DifferentialAnalyzer struct{}

// NewDifferentialAnalyzer creates a new differential analyzer
func NewDifferentialAnalyzer() *DifferentialAnalyzer {
	return &DifferentialAnalyzer{}
}

// Compare compares two responses
func (da *DifferentialAnalyzer) Compare(baseline, response []byte) *DiffResult {
	result := &DiffResult{
		BaselineLen: len(baseline),
		ResponseLen: len(response),
		LengthDiff:  len(response) - len(baseline),
	}

	// Check for significant differences
	if result.LengthDiff != 0 {
		result.HasDifference = true
	}

	// Check content similarity
	if len(baseline) > 0 && len(response) > 0 {
		similarity := da.calculateSimilarity(baseline, response)
		result.Similarity = similarity
		if similarity < 0.9 {
			result.HasDifference = true
		}
	}

	return result
}

// calculateSimilarity calculates content similarity (simple version)
func (da *DifferentialAnalyzer) calculateSimilarity(a, b []byte) float64 {
	if len(a) == 0 || len(b) == 0 {
		return 0
	}

	// Simple length-based similarity as placeholder
	minLen := len(a)
	if len(b) < minLen {
		minLen = len(b)
	}
	maxLen := len(a)
	if len(b) > maxLen {
		maxLen = len(b)
	}

	return float64(minLen) / float64(maxLen)
}

// DiffResult represents differential analysis result
type DiffResult struct {
	BaselineLen   int
	ResponseLen   int
	LengthDiff    int
	Similarity    float64
	HasDifference bool
}
