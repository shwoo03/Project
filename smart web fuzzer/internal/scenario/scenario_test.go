package scenario

import (
	"testing"
	"time"
)

// --- Mock implementations for testing ---

type mockHTTPClient struct {
	responses []*Response
	callIdx   int
	requests  []*Request
}

func newMockHTTPClient(responses ...*Response) *mockHTTPClient {
	return &mockHTTPClient{
		responses: responses,
		requests:  make([]*Request, 0),
	}
}

func (m *mockHTTPClient) Do(req *Request) (*Response, error) {
	m.requests = append(m.requests, req)
	if m.callIdx >= len(m.responses) {
		// Reuse last response if available (for infinite loop tests)
		if len(m.responses) > 0 {
			return m.responses[len(m.responses)-1], nil
		}
		return &Response{StatusCode: 500, Body: []byte("no more mocked responses")}, nil
	}
	resp := m.responses[m.callIdx]
	m.callIdx++
	return resp, nil
}

type mockSubstitutor struct {
	variables map[string]string
}

func newMockSubstitutor() *mockSubstitutor {
	return &mockSubstitutor{
		variables: make(map[string]string),
	}
}

func (m *mockSubstitutor) Substitute(input string) string {
	result := input
	for k, v := range m.variables {
		result = replaceAll(result, "{{"+k+"}}", v)
	}
	return result
}

func (m *mockSubstitutor) SetVariable(name, value string) {
	m.variables[name] = value
}

func replaceAll(s, old, new string) string {
	for {
		i := indexOf(s, old)
		if i < 0 {
			return s
		}
		s = s[:i] + new + s[i+len(old):]
	}
}

func indexOf(s, substr string) int {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return i
		}
	}
	return -1
}

// --- Parser Tests ---

func TestParser_Parse_BasicScenario(t *testing.T) {
	yaml := `
name: Login Flow
description: Test login and authenticated request
version: "1.0"
variables:
  base_url: "http://localhost:8080"
steps:
  - name: login
    request:
      method: POST
      url: "{{base_url}}/api/login"
      headers:
        Content-Type: application/json
      body: '{"username": "admin", "password": "secret"}'
    extract:
      - name: token
        type: jsonpath
        pattern: "access_token"
    assert:
      - type: status
        expected: "200"
`

	parser := NewParser()
	scenario, err := parser.Parse([]byte(yaml))

	if err != nil {
		t.Fatalf("Parse failed: %v", err)
	}

	if scenario.Name != "Login Flow" {
		t.Errorf("Expected name 'Login Flow', got '%s'", scenario.Name)
	}

	if len(scenario.Steps) != 1 {
		t.Fatalf("Expected 1 step, got %d", len(scenario.Steps))
	}

	step := scenario.Steps[0]
	if step.Name != "login" {
		t.Errorf("Expected step name 'login', got '%s'", step.Name)
	}

	if step.Request.Method != "POST" {
		t.Errorf("Expected method 'POST', got '%s'", step.Request.Method)
	}

	if len(step.Extract) != 1 {
		t.Errorf("Expected 1 extraction rule, got %d", len(step.Extract))
	}

	if len(step.Assert) != 1 {
		t.Errorf("Expected 1 assertion, got %d", len(step.Assert))
	}
}

func TestParser_Parse_MultiStep(t *testing.T) {
	yaml := `
name: Multi-Step Flow
steps:
  - name: step1
    request:
      method: GET
      url: http://example.com/api/1
  - name: step2
    request:
      method: GET
      url: http://example.com/api/2
    condition: "exists:token"
  - name: step3
    request:
      method: GET
      url: http://example.com/api/3
`

	parser := NewParser()
	scenario, err := parser.Parse([]byte(yaml))

	if err != nil {
		t.Fatalf("Parse failed: %v", err)
	}

	if len(scenario.Steps) != 3 {
		t.Fatalf("Expected 3 steps, got %d", len(scenario.Steps))
	}

	if scenario.Steps[1].Condition != "exists:token" {
		t.Errorf("Expected condition 'exists:token', got '%s'", scenario.Steps[1].Condition)
	}
}

func TestParser_Parse_ConditionalBranching(t *testing.T) {
	yaml := `
name: Branching Flow
steps:
  - name: check_status
    request:
      method: GET
      url: http://example.com/status
    on_success: success_step
    on_failure: failure_step
  - name: success_step
    request:
      method: GET
      url: http://example.com/success
  - name: failure_step
    request:
      method: GET
      url: http://example.com/failure
`

	parser := NewParser()
	scenario, err := parser.Parse([]byte(yaml))

	if err != nil {
		t.Fatalf("Parse failed: %v", err)
	}

	if !scenario.HasConditionalFlow() {
		t.Error("Expected HasConditionalFlow() to return true")
	}

	step := scenario.Steps[0]
	if step.OnSuccess != "success_step" {
		t.Errorf("Expected on_success 'success_step', got '%s'", step.OnSuccess)
	}
	if step.OnFailure != "failure_step" {
		t.Errorf("Expected on_failure 'failure_step', got '%s'", step.OnFailure)
	}
}

func TestParser_Validate_EmptyName(t *testing.T) {
	yaml := `
name: ""
steps:
  - name: step1
    request:
      method: GET
      url: http://example.com
`

	parser := NewParser()
	_, err := parser.Parse([]byte(yaml))

	if err == nil {
		t.Error("Expected validation error for empty name")
	}
}

func TestParser_Validate_DuplicateStepName(t *testing.T) {
	yaml := `
name: Test
steps:
  - name: duplicate
    request:
      method: GET
      url: http://example.com/1
  - name: duplicate
    request:
      method: GET
      url: http://example.com/2
`

	parser := NewParser()
	_, err := parser.Parse([]byte(yaml))

	if err == nil {
		t.Error("Expected validation error for duplicate step name")
	}
}

func TestParser_Validate_InvalidStepReference(t *testing.T) {
	yaml := `
name: Test
steps:
  - name: step1
    request:
      method: GET
      url: http://example.com
    on_success: nonexistent_step
`

	parser := NewParser()
	_, err := parser.Parse([]byte(yaml))

	if err == nil {
		t.Error("Expected validation error for invalid step reference")
	}
}

func TestParser_ApplyDefaults(t *testing.T) {
	yaml := `
name: Defaults Test
steps:
  - name: step1
    request:
      url: http://example.com
`

	parser := NewParser()
	scenario, err := parser.Parse([]byte(yaml))

	if err != nil {
		t.Fatalf("Parse failed: %v", err)
	}

	step := scenario.Steps[0]

	// Default method should be GET
	if step.Request.Method != "GET" {
		t.Errorf("Expected default method 'GET', got '%s'", step.Request.Method)
	}

	// Default timeout should be 30s
	if step.Request.Timeout != 30*time.Second {
		t.Errorf("Expected default timeout 30s, got %v", step.Request.Timeout)
	}
}

// --- Scenario Tests ---

func TestScenario_GetStepByName(t *testing.T) {
	scenario := &Scenario{
		Name: "Test",
		Steps: []Step{
			{Name: "step1", Request: RequestConfig{Method: "GET", URL: "http://1"}},
			{Name: "step2", Request: RequestConfig{Method: "GET", URL: "http://2"}},
			{Name: "step3", Request: RequestConfig{Method: "GET", URL: "http://3"}},
		},
	}

	step, idx := scenario.GetStepByName("step2")
	if step == nil || idx != 1 {
		t.Errorf("Expected step2 at index 1, got step=%v, idx=%d", step, idx)
	}

	step, idx = scenario.GetStepByName("nonexistent")
	if step != nil || idx != -1 {
		t.Errorf("Expected nil step and -1 index for nonexistent step")
	}
}

func TestScenario_GetStepNames(t *testing.T) {
	scenario := &Scenario{
		Name: "Test",
		Steps: []Step{
			{Name: "a", Request: RequestConfig{Method: "GET", URL: "http://a"}},
			{Name: "b", Request: RequestConfig{Method: "GET", URL: "http://b"}},
			{Name: "c", Request: RequestConfig{Method: "GET", URL: "http://c"}},
		},
	}

	names := scenario.GetStepNames()
	if len(names) != 3 || names[0] != "a" || names[1] != "b" || names[2] != "c" {
		t.Errorf("Unexpected step names: %v", names)
	}
}

func TestScenario_Clone(t *testing.T) {
	original := &Scenario{
		Name:        "Original",
		Description: "Test",
		Variables:   map[string]string{"key": "value"},
		Steps: []Step{
			{Name: "step1", Request: RequestConfig{Method: "GET", URL: "http://test"}},
		},
	}

	clone := original.Clone()

	if clone.Name != original.Name {
		t.Error("Clone should have same name")
	}

	// Modify clone variables
	clone.Variables["key"] = "modified"

	if original.Variables["key"] != "value" {
		t.Error("Modifying clone should not affect original variables")
	}
}

// --- Executor Tests ---

func TestExecutor_Execute_SimpleScenario(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 200, Body: []byte(`{"message":"ok"}`), Duration: 100 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()

	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "Simple Test",
		Steps: []Step{
			{
				Name: "test_step",
				Request: RequestConfig{
					Method: "GET",
					URL:    "http://example.com/api",
				},
				Assert: []Assertion{
					{Type: AssertStatus, Expected: "200"},
				},
			},
		},
	}

	result, err := executor.Execute(scenario)

	if err != nil {
		t.Fatalf("Execute failed: %v", err)
	}

	if !result.Success {
		t.Errorf("Expected success, got failure: %s", result.Error)
	}

	if len(result.StepResults) != 1 {
		t.Fatalf("Expected 1 step result, got %d", len(result.StepResults))
	}

	if result.StepResults[0].StatusCode != 200 {
		t.Errorf("Expected status 200, got %d", result.StepResults[0].StatusCode)
	}
}

func TestExecutor_Execute_WithExtraction(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 200, Body: []byte(`{"token":"abc123"}`), Duration: 50 * time.Millisecond},
		&Response{StatusCode: 200, Body: []byte(`{"data":"protected"}`), Duration: 50 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()

	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "Extraction Test",
		Steps: []Step{
			{
				Name: "login",
				Request: RequestConfig{
					Method: "POST",
					URL:    "http://example.com/login",
				},
				Extract: []ExtractionRule{
					{Name: "auth_token", Type: "jsonpath", Pattern: "token"},
				},
			},
			{
				Name: "get_data",
				Request: RequestConfig{
					Method: "GET",
					URL:    "http://example.com/data?token={{auth_token}}",
				},
			},
		},
	}

	result, err := executor.Execute(scenario)

	if err != nil {
		t.Fatalf("Execute failed: %v", err)
	}

	if !result.Success {
		t.Errorf("Expected success, got failure: %s", result.Error)
	}

	// Check extraction
	if result.Variables["auth_token"] != "abc123" {
		t.Errorf("Expected auth_token='abc123', got '%s'", result.Variables["auth_token"])
	}

	// Check substitution was applied
	if len(client.requests) < 2 {
		t.Fatal("Expected at least 2 requests")
	}

	secondReq := client.requests[1]
	if secondReq.URL != "http://example.com/data?token=abc123" {
		t.Errorf("Expected substituted URL, got '%s'", secondReq.URL)
	}
}

func TestExecutor_Execute_ConditionalBranch(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 200, Body: []byte(`{}`), Duration: 10 * time.Millisecond},
		&Response{StatusCode: 200, Body: []byte(`{}`), Duration: 10 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()

	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "Branch Test",
		Steps: []Step{
			{
				Name:      "first",
				Request:   RequestConfig{Method: "GET", URL: "http://example.com/1"},
				Assert:    []Assertion{{Type: AssertStatus, Expected: "200"}},
				OnSuccess: "success_path",
			},
			{
				Name:    "failure_path",
				Request: RequestConfig{Method: "GET", URL: "http://example.com/fail"},
			},
			{
				Name:    "success_path",
				Request: RequestConfig{Method: "GET", URL: "http://example.com/success"},
			},
		},
	}

	result, err := executor.Execute(scenario)

	if err != nil {
		t.Fatalf("Execute failed: %v", err)
	}

	// Should have executed first and success_path, skipping failure_path
	if len(result.StepResults) != 2 {
		t.Fatalf("Expected 2 step results, got %d", len(result.StepResults))
	}

	if result.StepResults[0].StepName != "first" {
		t.Errorf("Expected first step 'first', got '%s'", result.StepResults[0].StepName)
	}

	if result.StepResults[1].StepName != "success_path" {
		t.Errorf("Expected second step 'success_path', got '%s'", result.StepResults[1].StepName)
	}
}

func TestExecutor_Execute_ConditionSkip(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 200, Body: []byte(`{}`), Duration: 10 * time.Millisecond},
		&Response{StatusCode: 200, Body: []byte(`{}`), Duration: 10 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()
	// Do not set 'token' variable, so condition should fail

	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "Condition Test",
		Steps: []Step{
			{
				Name:    "always_run",
				Request: RequestConfig{Method: "GET", URL: "http://example.com/1"},
			},
			{
				Name:      "conditional",
				Request:   RequestConfig{Method: "GET", URL: "http://example.com/2"},
				Condition: "exists:token",
			},
			{
				Name:    "final",
				Request: RequestConfig{Method: "GET", URL: "http://example.com/3"},
			},
		},
	}

	result, err := executor.Execute(scenario)

	if err != nil {
		t.Fatalf("Execute failed: %v", err)
	}

	// Should skip conditional step
	if len(result.StepResults) != 2 {
		t.Fatalf("Expected 2 step results (skipping conditional), got %d", len(result.StepResults))
	}

	if result.StepResults[0].StepName != "always_run" {
		t.Errorf("Expected first step 'always_run', got '%s'", result.StepResults[0].StepName)
	}

	if result.StepResults[1].StepName != "final" {
		t.Errorf("Expected second step 'final', got '%s'", result.StepResults[1].StepName)
	}
}

func TestExecutor_Execute_AssertionFailure(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 404, Body: []byte(`{"error":"not found"}`), Duration: 10 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()

	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "Assertion Failure Test",
		Steps: []Step{
			{
				Name:    "failing_step",
				Request: RequestConfig{Method: "GET", URL: "http://example.com/api"},
				Assert: []Assertion{
					{Type: AssertStatus, Expected: "200"},
				},
			},
		},
	}

	result, err := executor.Execute(scenario)

	if err != nil {
		t.Fatalf("Execute failed: %v", err)
	}

	if result.Success {
		t.Error("Expected failure due to assertion")
	}

	if len(result.StepResults) != 1 {
		t.Fatalf("Expected 1 step result, got %d", len(result.StepResults))
	}

	stepResult := result.StepResults[0]
	if stepResult.Success {
		t.Error("Step should have failed")
	}

	if len(stepResult.Assertions) != 1 {
		t.Fatalf("Expected 1 assertion result, got %d", len(stepResult.Assertions))
	}

	if stepResult.Assertions[0].Passed {
		t.Error("Assertion should have failed")
	}
}

func TestExecutor_Execute_Retry(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 500, Body: []byte(`error`), Duration: 10 * time.Millisecond},
		&Response{StatusCode: 500, Body: []byte(`error`), Duration: 10 * time.Millisecond},
		&Response{StatusCode: 200, Body: []byte(`ok`), Duration: 10 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()

	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "Retry Test",
		Steps: []Step{
			{
				Name:    "retry_step",
				Request: RequestConfig{Method: "GET", URL: "http://example.com/api"},
				Assert: []Assertion{
					{Type: AssertStatus, Expected: "200"},
				},
				Retry: &RetryConfig{
					Count:    3,
					Delay:    10 * time.Millisecond,
					OnStatus: []int{500},
				},
			},
		},
	}

	result, err := executor.Execute(scenario)

	if err != nil {
		t.Fatalf("Execute failed: %v", err)
	}

	if !result.Success {
		t.Errorf("Expected success after retry, got failure: %s", result.Error)
	}

	if len(client.requests) != 3 {
		t.Errorf("Expected 3 requests (initial + 2 retries), got %d", len(client.requests))
	}

	if result.StepResults[0].RetryCount != 2 {
		t.Errorf("Expected retry count 2, got %d", result.StepResults[0].RetryCount)
	}
}

func TestExecutor_Execute_MaxSteps(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 200, Body: []byte(`ok`), Duration: 1 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()

	// Create infinite loop scenario
	scenario := &Scenario{
		Name: "Infinite Loop",
		Steps: []Step{
			{
				Name:      "loop",
				Request:   RequestConfig{Method: "GET", URL: "http://example.com"},
				Assert:    []Assertion{{Type: AssertStatus, Expected: "200"}},
				OnSuccess: "loop", // Points to itself
			},
		},
	}

	executor := NewExecutor(client, substitutor, WithMaxSteps(5))

	result, err := executor.Execute(scenario)

	if err != nil {
		t.Fatalf("Execute failed: %v", err)
	}

	if result.Success {
		t.Error("Expected failure due to max steps exceeded")
	}

	if result.Error != "max steps exceeded (possible infinite loop)" {
		t.Errorf("Expected max steps error, got: %s", result.Error)
	}
}

// --- Assertion Tests ---

func TestAssertion_Contains(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 200, Body: []byte(`Hello World`), Duration: 10 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()
	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "Contains Test",
		Steps: []Step{
			{
				Name:    "test",
				Request: RequestConfig{Method: "GET", URL: "http://example.com"},
				Assert: []Assertion{
					{Type: AssertContains, Expected: "World"},
					{Type: AssertNotContains, Expected: "Goodbye"},
				},
			},
		},
	}

	result, _ := executor.Execute(scenario)

	if !result.Success {
		t.Errorf("Expected success, got: %s", result.Error)
	}
}

func TestAssertion_Regex(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 200, Body: []byte(`ID: 12345`), Duration: 10 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()
	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "Regex Test",
		Steps: []Step{
			{
				Name:    "test",
				Request: RequestConfig{Method: "GET", URL: "http://example.com"},
				Assert: []Assertion{
					{Type: AssertRegex, Expected: `ID: \d+`},
				},
			},
		},
	}

	result, _ := executor.Execute(scenario)

	if !result.Success {
		t.Errorf("Expected success, got: %s", result.Error)
	}
}

func TestAssertion_JSONPath(t *testing.T) {
	client := newMockHTTPClient(
		&Response{StatusCode: 200, Body: []byte(`{"user":{"name":"Alice"}}`), Duration: 10 * time.Millisecond},
	)
	substitutor := newMockSubstitutor()
	executor := NewExecutor(client, substitutor)

	scenario := &Scenario{
		Name: "JSONPath Test",
		Steps: []Step{
			{
				Name:    "test",
				Request: RequestConfig{Method: "GET", URL: "http://example.com"},
				Assert: []Assertion{
					{Type: AssertJSONPath, Target: "user.name", Expected: "Alice"},
				},
			},
		},
	}

	result, _ := executor.Execute(scenario)

	if !result.Success {
		t.Errorf("Expected success, got: %s", result.Error)
	}
}

// --- Benchmark Tests ---

func BenchmarkParser_Parse(b *testing.B) {
	yaml := []byte(`
name: Benchmark Scenario
steps:
  - name: step1
    request:
      method: GET
      url: http://example.com/api
    assert:
      - type: status
        expected: "200"
`)

	parser := NewParser()
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		parser.Parse(yaml)
	}
}

func BenchmarkExecutor_Execute(b *testing.B) {
	scenario := &Scenario{
		Name: "Benchmark",
		Steps: []Step{
			{
				Name:    "step1",
				Request: RequestConfig{Method: "GET", URL: "http://example.com"},
				Assert:  []Assertion{{Type: AssertStatus, Expected: "200"}},
			},
		},
	}

	substitutor := newMockSubstitutor()

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		client := newMockHTTPClient(
			&Response{StatusCode: 200, Body: []byte(`ok`), Duration: 1 * time.Millisecond},
		)
		executor := NewExecutor(client, substitutor)
		executor.Execute(scenario)
	}
}
