// Package owasp provides OWASP Top 10 vulnerability detection.
package owasp

import (
	"context"
	"sync"
	"time"
)

// VulnerabilityType represents OWASP Top 10 vulnerability types
type VulnerabilityType string

const (
	// A01:2021 - Broken Access Control
	BrokenAccessControl VulnerabilityType = "A01_BROKEN_ACCESS_CONTROL"
	IDOR                VulnerabilityType = "A01_IDOR"
	PrivilegeEscalation VulnerabilityType = "A01_PRIVILEGE_ESCALATION"
	ForcedbBrowsing     VulnerabilityType = "A01_FORCED_BROWSING"

	// A02:2021 - Cryptographic Failures
	CryptographicFailures VulnerabilityType = "A02_CRYPTOGRAPHIC_FAILURES"
	WeakCrypto            VulnerabilityType = "A02_WEAK_CRYPTO"
	SensitiveDataExposure VulnerabilityType = "A02_SENSITIVE_DATA_EXPOSURE"

	// A03:2021 - Injection
	SQLInjection   VulnerabilityType = "A03_SQL_INJECTION"
	NoSQLInjection VulnerabilityType = "A03_NOSQL_INJECTION"
	LDAPInjection  VulnerabilityType = "A03_LDAP_INJECTION"
	OSCommand      VulnerabilityType = "A03_OS_COMMAND"
	XSS            VulnerabilityType = "A03_XSS"

	// A04:2021 - Insecure Design
	InsecureDesign      VulnerabilityType = "A04_INSECURE_DESIGN"
	MissingRateLimiting VulnerabilityType = "A04_MISSING_RATE_LIMITING"
	BusinessLogicFlaw   VulnerabilityType = "A04_BUSINESS_LOGIC_FLAW"

	// A05:2021 - Security Misconfiguration
	SecurityMisconfig  VulnerabilityType = "A05_SECURITY_MISCONFIG"
	DefaultCredentials VulnerabilityType = "A05_DEFAULT_CREDENTIALS"
	DirectoryListing   VulnerabilityType = "A05_DIRECTORY_LISTING"
	VerboseErrors      VulnerabilityType = "A05_VERBOSE_ERRORS"
	XXE                VulnerabilityType = "A05_XXE"

	// A06:2021 - Vulnerable Components
	VulnerableComponents VulnerabilityType = "A06_VULNERABLE_COMPONENTS"
	OutdatedLibrary      VulnerabilityType = "A06_OUTDATED_LIBRARY"

	// A07:2021 - Authentication Failures
	AuthenticationFailures VulnerabilityType = "A07_AUTH_FAILURES"
	WeakPassword           VulnerabilityType = "A07_WEAK_PASSWORD"
	BruteForce             VulnerabilityType = "A07_BRUTE_FORCE"
	SessionFixation        VulnerabilityType = "A07_SESSION_FIXATION"

	// A08:2021 - Data Integrity Failures
	DataIntegrityFailures   VulnerabilityType = "A08_DATA_INTEGRITY"
	InsecureDeserialization VulnerabilityType = "A08_INSECURE_DESERIALIZATION"

	// A09:2021 - Security Logging Failures
	LoggingFailures VulnerabilityType = "A09_LOGGING_FAILURES"

	// A10:2021 - SSRF
	SSRF VulnerabilityType = "A10_SSRF"
)

// Severity levels
type Severity string

const (
	Critical Severity = "critical"
	High     Severity = "high"
	Medium   Severity = "medium"
	Low      Severity = "low"
	Info     Severity = "info"
)

// Finding represents a detected vulnerability
type Finding struct {
	Type        VulnerabilityType `json:"type"`
	Severity    Severity          `json:"severity"`
	URL         string            `json:"url"`
	Method      string            `json:"method"`
	Parameter   string            `json:"parameter"`
	Payload     string            `json:"payload"`
	Evidence    string            `json:"evidence"`
	Description string            `json:"description"`
	Remediation string            `json:"remediation"`
	CWE         string            `json:"cwe"`
	CVSS        float64           `json:"cvss"`
	Confidence  float64           `json:"confidence"`
	Timestamp   time.Time         `json:"timestamp"`
}

// Detector is the main vulnerability detector
type Detector struct {
	checkers []VulnerabilityChecker
	findings []*Finding
	config   *DetectorConfig
	stats    *DetectorStats
	mu       sync.RWMutex
}

// DetectorConfig holds detector configuration
type DetectorConfig struct {
	EnabledChecks   []VulnerabilityType
	MaxConcurrency  int
	Timeout         time.Duration
	FollowRedirects bool
	MaxRedirects    int
	UserAgent       string
}

// DefaultDetectorConfig returns default configuration
func DefaultDetectorConfig() *DetectorConfig {
	return &DetectorConfig{
		EnabledChecks:   nil, // All enabled
		MaxConcurrency:  10,
		Timeout:         30 * time.Second,
		FollowRedirects: true,
		MaxRedirects:    5,
		UserAgent:       "FluxFuzzer/1.0",
	}
}

// DetectorStats holds detection statistics
type DetectorStats struct {
	TotalChecks int64                       `json:"total_checks"`
	Findings    int64                       `json:"findings"`
	BySeverity  map[Severity]int64          `json:"by_severity"`
	ByType      map[VulnerabilityType]int64 `json:"by_type"`
	Duration    time.Duration               `json:"duration"`
}

// VulnerabilityChecker interface for vulnerability checks
type VulnerabilityChecker interface {
	Check(ctx context.Context, target *Target) ([]*Finding, error)
	Type() VulnerabilityType
	Name() string
}

// Target represents a scan target
type Target struct {
	URL        string
	Method     string
	Headers    map[string]string
	Parameters map[string]string
	Body       []byte
	Cookies    map[string]string
}

// NewDetector creates a new detector
func NewDetector(config *DetectorConfig) *Detector {
	if config == nil {
		config = DefaultDetectorConfig()
	}

	d := &Detector{
		checkers: make([]VulnerabilityChecker, 0),
		findings: make([]*Finding, 0),
		config:   config,
		stats: &DetectorStats{
			BySeverity: make(map[Severity]int64),
			ByType:     make(map[VulnerabilityType]int64),
		},
	}

	// Register default checkers
	d.registerDefaultCheckers()

	return d
}

// registerDefaultCheckers registers all default vulnerability checkers
func (d *Detector) registerDefaultCheckers() {
	d.RegisterChecker(NewSQLInjectionChecker())
	d.RegisterChecker(NewXSSChecker())
	d.RegisterChecker(NewSSRFChecker())
	d.RegisterChecker(NewIDORChecker())
	d.RegisterChecker(NewXXEChecker())
	d.RegisterChecker(NewCommandInjectionChecker())
	d.RegisterChecker(NewAuthChecker())
	d.RegisterChecker(NewMisconfigChecker())
	d.RegisterChecker(NewCryptoChecker())
	d.RegisterChecker(NewDeserializationChecker())
}

// RegisterChecker registers a vulnerability checker
func (d *Detector) RegisterChecker(checker VulnerabilityChecker) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.checkers = append(d.checkers, checker)
}

// Scan scans a target for vulnerabilities
func (d *Detector) Scan(ctx context.Context, target *Target) ([]*Finding, error) {
	startTime := time.Now()
	var allFindings []*Finding
	var wg sync.WaitGroup
	findingsChan := make(chan []*Finding, len(d.checkers))
	sem := make(chan struct{}, d.config.MaxConcurrency)

	for _, checker := range d.checkers {
		// Check if this checker is enabled
		if !d.isCheckerEnabled(checker.Type()) {
			continue
		}

		wg.Add(1)
		go func(c VulnerabilityChecker) {
			defer wg.Done()

			sem <- struct{}{}
			defer func() { <-sem }()

			findings, err := c.Check(ctx, target)
			if err == nil && len(findings) > 0 {
				findingsChan <- findings
			}
		}(checker)
	}

	// Close channel when all done
	go func() {
		wg.Wait()
		close(findingsChan)
	}()

	// Collect findings
	for findings := range findingsChan {
		allFindings = append(allFindings, findings...)
	}

	// Update stats
	d.mu.Lock()
	d.findings = append(d.findings, allFindings...)
	d.stats.TotalChecks++
	d.stats.Duration = time.Since(startTime)

	for _, f := range allFindings {
		d.stats.Findings++
		d.stats.BySeverity[f.Severity]++
		d.stats.ByType[f.Type]++
	}
	d.mu.Unlock()

	return allFindings, nil
}

// isCheckerEnabled checks if a checker type is enabled
func (d *Detector) isCheckerEnabled(t VulnerabilityType) bool {
	if len(d.config.EnabledChecks) == 0 {
		return true // All enabled if none specified
	}

	for _, enabled := range d.config.EnabledChecks {
		if enabled == t {
			return true
		}
	}
	return false
}

// GetFindings returns all findings
func (d *Detector) GetFindings() []*Finding {
	d.mu.RLock()
	defer d.mu.RUnlock()

	findings := make([]*Finding, len(d.findings))
	copy(findings, d.findings)
	return findings
}

// GetStats returns detection statistics
func (d *Detector) GetStats() DetectorStats {
	d.mu.RLock()
	defer d.mu.RUnlock()

	stats := DetectorStats{
		TotalChecks: d.stats.TotalChecks,
		Findings:    d.stats.Findings,
		Duration:    d.stats.Duration,
		BySeverity:  make(map[Severity]int64),
		ByType:      make(map[VulnerabilityType]int64),
	}

	for k, v := range d.stats.BySeverity {
		stats.BySeverity[k] = v
	}
	for k, v := range d.stats.ByType {
		stats.ByType[k] = v
	}

	return stats
}

// ClearFindings clears all findings
func (d *Detector) ClearFindings() {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.findings = make([]*Finding, 0)
}

// GetCheckerCount returns the number of registered checkers
func (d *Detector) GetCheckerCount() int {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return len(d.checkers)
}
