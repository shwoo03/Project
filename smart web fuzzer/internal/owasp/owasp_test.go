package owasp

import (
	"context"
	"testing"
)

func TestDetector(t *testing.T) {
	detector := NewDetector(nil)

	if detector.GetCheckerCount() == 0 {
		t.Error("Should have registered checkers")
	}

	target := &Target{
		URL:    "http://example.com/api",
		Method: "GET",
		Parameters: map[string]string{
			"id":    "1",
			"query": "test",
		},
	}

	ctx := context.Background()
	findings, err := detector.Scan(ctx, target)
	if err != nil {
		t.Fatalf("Scan failed: %v", err)
	}

	t.Logf("Found %d findings", len(findings))

	stats := detector.GetStats()
	if stats.TotalChecks != 1 {
		t.Errorf("Expected 1 check, got %d", stats.TotalChecks)
	}
}

func TestDetector_EnabledChecks(t *testing.T) {
	config := &DetectorConfig{
		EnabledChecks: []VulnerabilityType{SQLInjection},
	}
	detector := NewDetector(config)

	target := &Target{
		URL:    "http://example.com/api",
		Method: "GET",
		Parameters: map[string]string{
			"id": "1",
		},
	}

	ctx := context.Background()
	findings, _ := detector.Scan(ctx, target)

	// Should only have SQL injection findings
	for _, f := range findings {
		if f.Type != SQLInjection {
			t.Errorf("Unexpected finding type: %s", f.Type)
		}
	}
}

func TestSQLInjectionChecker(t *testing.T) {
	checker := NewSQLInjectionChecker()

	if checker.Type() != SQLInjection {
		t.Error("Wrong type")
	}

	if checker.Name() == "" {
		t.Error("Empty name")
	}

	target := &Target{
		URL:    "http://example.com/api",
		Method: "GET",
		Parameters: map[string]string{
			"id": "1",
		},
	}

	ctx := context.Background()
	findings, err := checker.Check(ctx, target)
	if err != nil {
		t.Fatalf("Check failed: %v", err)
	}

	if len(findings) == 0 {
		t.Error("Should generate SQLi payloads")
	}

	for _, f := range findings {
		if f.Parameter != "id" {
			t.Error("Wrong parameter")
		}
		if f.Severity != Critical {
			t.Error("SQL injection should be critical")
		}
	}
}

func TestXSSChecker(t *testing.T) {
	checker := NewXSSChecker()

	target := &Target{
		URL:    "http://example.com/search",
		Method: "GET",
		Parameters: map[string]string{
			"q": "test",
		},
	}

	ctx := context.Background()
	findings, err := checker.Check(ctx, target)
	if err != nil {
		t.Fatalf("Check failed: %v", err)
	}

	if len(findings) == 0 {
		t.Error("Should generate XSS payloads")
	}

	for _, f := range findings {
		if f.Severity != High {
			t.Error("XSS should be high severity")
		}
	}
}

func TestSSRFChecker(t *testing.T) {
	checker := NewSSRFChecker()

	target := &Target{
		URL:    "http://example.com/fetch",
		Method: "POST",
		Parameters: map[string]string{
			"url": "http://example.org",
		},
	}

	ctx := context.Background()
	findings, err := checker.Check(ctx, target)
	if err != nil {
		t.Fatalf("Check failed: %v", err)
	}

	if len(findings) == 0 {
		t.Error("Should detect URL parameter for SSRF testing")
	}
}

func TestIDORChecker(t *testing.T) {
	checker := NewIDORChecker()

	target := &Target{
		URL:    "http://example.com/user",
		Method: "GET",
		Parameters: map[string]string{
			"user_id": "123",
		},
	}

	ctx := context.Background()
	findings, err := checker.Check(ctx, target)
	if err != nil {
		t.Fatalf("Check failed: %v", err)
	}

	if len(findings) == 0 {
		t.Error("Should detect ID parameter for IDOR testing")
	}
}

func TestXXEChecker(t *testing.T) {
	checker := NewXXEChecker()

	target := &Target{
		URL:    "http://example.com/api",
		Method: "POST",
		Body:   []byte(`<?xml version="1.0"?><root><data>test</data></root>`),
	}

	ctx := context.Background()
	findings, err := checker.Check(ctx, target)
	if err != nil {
		t.Fatalf("Check failed: %v", err)
	}

	if len(findings) == 0 {
		t.Error("Should detect XML body for XXE testing")
	}
}

func TestCommandInjectionChecker(t *testing.T) {
	checker := NewCommandInjectionChecker()

	target := &Target{
		URL:    "http://example.com/ping",
		Method: "GET",
		Parameters: map[string]string{
			"host": "localhost",
		},
	}

	ctx := context.Background()
	findings, err := checker.Check(ctx, target)
	if err != nil {
		t.Fatalf("Check failed: %v", err)
	}

	if len(findings) == 0 {
		t.Error("Should detect host parameter for command injection")
	}
}

func TestResponseAnalyzer(t *testing.T) {
	analyzer := NewResponseAnalyzer()

	// Test SQL error detection
	sqlError := []byte(`Error: You have an error in your SQL syntax near`)
	results := analyzer.Analyze(sqlError, SQLInjection)
	if len(results) == 0 {
		t.Error("Should detect SQL error")
	}

	// Test XSS detection
	xssReflected := []byte(`<script>alert(1)</script>`)
	results = analyzer.Analyze(xssReflected, XSS)
	if len(results) == 0 {
		t.Error("Should detect reflected XSS")
	}

	// Test command injection detection
	cmdOutput := []byte(`uid=1000(user) gid=1000(user)`)
	results = analyzer.Analyze(cmdOutput, OSCommand)
	if len(results) == 0 {
		t.Error("Should detect command output")
	}
}

func TestResponseAnalyzer_AnalyzeAll(t *testing.T) {
	analyzer := NewResponseAnalyzer()

	// Response with multiple issues
	body := []byte(`
		Error: SQL syntax error near 'test'
		<script>alert(1)</script>
		uid=0(root) gid=0(root)
	`)

	results := analyzer.AnalyzeAll(body)
	if len(results) < 3 {
		t.Errorf("Should detect multiple issues, got %d", len(results))
	}
}

func TestHeaderAnalyzer(t *testing.T) {
	analyzer := NewHeaderAnalyzer()

	// Missing security headers
	headers := map[string]string{
		"Content-Type": "text/html",
	}

	findings := analyzer.AnalyzeHeaders(headers)
	if len(findings) == 0 {
		t.Error("Should detect missing security headers")
	}

	// Check specific missing headers
	foundHSTS := false
	foundCSP := false
	for _, f := range findings {
		if f.Header == "Strict-Transport-Security" {
			foundHSTS = true
		}
		if f.Header == "Content-Security-Policy" {
			foundCSP = true
		}
	}

	if !foundHSTS {
		t.Error("Should detect missing HSTS header")
	}
	if !foundCSP {
		t.Error("Should detect missing CSP header")
	}
}

func TestHeaderAnalyzer_ServerDisclosure(t *testing.T) {
	analyzer := NewHeaderAnalyzer()

	headers := map[string]string{
		"Server":       "Apache/2.4.41 (Ubuntu)",
		"X-Powered-By": "PHP/7.4.3",
	}

	findings := analyzer.AnalyzeHeaders(headers)

	foundServer := false
	foundPoweredBy := false
	for _, f := range findings {
		if f.Header == "Server" {
			foundServer = true
		}
		if f.Header == "X-Powered-By" {
			foundPoweredBy = true
		}
	}

	if !foundServer {
		t.Error("Should detect Server header disclosure")
	}
	if !foundPoweredBy {
		t.Error("Should detect X-Powered-By header disclosure")
	}
}

func TestTimingAnalyzer(t *testing.T) {
	analyzer := NewTimingAnalyzer(100) // 100ms baseline

	// Normal response
	result := analyzer.Analyze(150)
	if result.IsSuspicious {
		t.Error("1.5x baseline should not be suspicious")
	}

	// Slow response (potential timing attack)
	result = analyzer.Analyze(500)
	if !result.IsSuspicious {
		t.Error("5x baseline should be suspicious")
	}

	if result.Ratio != 5.0 {
		t.Errorf("Expected ratio 5.0, got %f", result.Ratio)
	}
}

func TestDifferentialAnalyzer(t *testing.T) {
	analyzer := NewDifferentialAnalyzer()

	baseline := []byte("Normal response content")
	similar := []byte("Normal response content")
	different := []byte("Error: SQL syntax error")

	// Same content
	result := analyzer.Compare(baseline, similar)
	if result.HasDifference {
		t.Error("Same content should not have difference")
	}

	// Different content
	result = analyzer.Compare(baseline, different)
	if !result.HasDifference {
		t.Error("Different content should have difference")
	}
}

func TestVulnerabilityTypes(t *testing.T) {
	types := []VulnerabilityType{
		BrokenAccessControl,
		CryptographicFailures,
		SQLInjection,
		InsecureDesign,
		SecurityMisconfig,
		VulnerableComponents,
		AuthenticationFailures,
		DataIntegrityFailures,
		LoggingFailures,
		SSRF,
	}

	for _, vt := range types {
		if vt == "" {
			t.Error("Empty vulnerability type")
		}
	}
}

func TestSeverityLevels(t *testing.T) {
	severities := []Severity{Critical, High, Medium, Low, Info}

	for _, s := range severities {
		if s == "" {
			t.Error("Empty severity")
		}
	}
}

func TestPayloads(t *testing.T) {
	if len(SQLInjectionPayloads) == 0 {
		t.Error("No SQL injection payloads")
	}
	if len(XSSPayloads) == 0 {
		t.Error("No XSS payloads")
	}
	if len(SSRFPayloads) == 0 {
		t.Error("No SSRF payloads")
	}
	if len(XXEPayloads) == 0 {
		t.Error("No XXE payloads")
	}
	if len(CommandInjectionPayloads) == 0 {
		t.Error("No command injection payloads")
	}
}

func TestDefaultCredentialsList(t *testing.T) {
	if len(DefaultCredentialsList) == 0 {
		t.Error("No default credentials")
	}

	// Check admin:admin exists
	found := false
	for _, cred := range DefaultCredentialsList {
		if cred.Username == "admin" && cred.Password == "admin" {
			found = true
			break
		}
	}

	if !found {
		t.Error("Should have admin:admin credentials")
	}
}

func BenchmarkResponseAnalyzer(b *testing.B) {
	analyzer := NewResponseAnalyzer()
	body := []byte(`
		Error: You have an error in your SQL syntax near 'test'
		at line 1 in /var/www/html/index.php
	`)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		analyzer.AnalyzeAll(body)
	}
}

func BenchmarkDetectorScan(b *testing.B) {
	detector := NewDetector(nil)
	target := &Target{
		URL:    "http://example.com/api",
		Method: "GET",
		Parameters: map[string]string{
			"id":    "1",
			"query": "test",
		},
	}
	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		detector.Scan(ctx, target)
	}
}
