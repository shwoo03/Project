package owasp

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// PrivilegeEscalationChecker checks for privilege escalation via cookie manipulation
type PrivilegeEscalationChecker struct{}

func NewPrivilegeEscalationChecker() *PrivilegeEscalationChecker {
	return &PrivilegeEscalationChecker{}
}
func (c *PrivilegeEscalationChecker) Type() VulnerabilityType { return BrokenAccessControl }
func (c *PrivilegeEscalationChecker) Name() string            { return "Privilege Escalation Checker" }

func (c *PrivilegeEscalationChecker) Check(ctx context.Context, target *Target) ([]*Finding, error) {
	var findings []*Finding

	client := &http.Client{
		Timeout: 5 * time.Second,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}

	// 1. Baseline Request
	req, err := http.NewRequest(target.Method, target.URL, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	baseBodyBytes, _ := io.ReadAll(resp.Body)
	baseBody := string(baseBodyBytes)

	// 2. Cookie Injection
	for _, cp := range CommonCookiePayloads {
		// Rate Limit Wait
		if err := WaitRateLimit(ctx); err != nil {
			return nil, err
		}

		// New request for each payload
		req, _ := http.NewRequest(target.Method, target.URL, nil)
		req.AddCookie(&http.Cookie{Name: cp.Name, Value: cp.Value})

		resp, err := client.Do(req)
		if err != nil {
			continue
		}

		bodyBytes, _ := io.ReadAll(resp.Body)
		body := string(bodyBytes)
		resp.Body.Close()

		// 3. Check for success indicators
		for _, ind := range SuccessIndicators {
			// Found in new body but NOT in base body
			if strings.Contains(body, ind) && !strings.Contains(baseBody, ind) {
				finding := &Finding{
					Type:        BrokenAccessControl,
					Severity:    Critical,
					URL:         target.URL,
					Method:      target.Method,
					Parameter:   "Cookie: " + cp.Name,
					Payload:     cp.Name + "=" + cp.Value,
					Description: fmt.Sprintf("권한 상승 취약점(Privilege Escalation) 탐지! '%s' 쿠키 주입 후 '%s' 문자열이 발견되었습니다.", cp.Name, ind),
					Remediation: "서버 측 세션 검증을 강화하고, 클라이언트가 조작 가능한 쿠키 값을 신뢰하여 권한을 부여하지 마십시오.",
					CWE:         "CWE-269",
					CVSS:        9.8,
					Confidence:  0.9,
					Evidence:    ind,
					Timestamp:   time.Now(),
				}
				findings = append(findings, finding)
				// One finding per payload is enough
				goto NextPayload
			}
		}
	NextPayload:
	}

	return findings, nil
}
