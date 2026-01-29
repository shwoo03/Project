package state

import (
	"os"
	"strings"
	"testing"
)

func TestTemplateEngine_SimpleVariable(t *testing.T) {
	e := NewTemplateEngine(nil)
	e.SetVariable("name", "Alice")
	e.SetVariable("id", "12345")

	result := e.Substitute("Hello {{name}}, your ID is {{id}}")
	expected := "Hello Alice, your ID is 12345"

	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func TestTemplateEngine_DefaultValue(t *testing.T) {
	e := NewTemplateEngine(nil)

	result := e.Substitute("Hello {{name:Guest}}")
	expected := "Hello Guest"

	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func TestTemplateEngine_PoolIntegration(t *testing.T) {
	pool := NewPool(nil)
	defer pool.Close()
	pool.Add("token", "abc123")

	e := NewTemplateEngine(pool)
	result := e.Substitute("Bearer {{token}}")
	expected := "Bearer abc123"

	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func TestTemplateEngine_RandomStr(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("Token: {{random_str(16)}}")

	if !strings.HasPrefix(result, "Token: ") {
		t.Errorf("Unexpected prefix in '%s'", result)
	}

	// Extract the random part
	token := strings.TrimPrefix(result, "Token: ")
	if len(token) != 16 {
		t.Errorf("Expected 16 char token, got %d: '%s'", len(token), token)
	}
}

func TestTemplateEngine_RandomInt(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("{{random_int(100, 200)}}")

	// Should be a number between 100 and 200
	if result == "" {
		t.Error("Expected non-empty result")
	}

	// Parse and verify range
	var n int
	if _, err := parseIntFromString(result, &n); err == nil {
		if n < 100 || n >= 200 {
			t.Errorf("Expected number in [100,200), got %d", n)
		}
	}
}

func parseIntFromString(s string, n *int) (string, error) {
	for i, c := range s {
		if c < '0' || c > '9' {
			return s[i:], nil
		}
		*n = *n*10 + int(c-'0')
	}
	return "", nil
}

func TestTemplateEngine_Timestamp(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("Time: {{timestamp()}}")

	if !strings.HasPrefix(result, "Time: ") {
		t.Errorf("Unexpected result: %s", result)
	}

	ts := strings.TrimPrefix(result, "Time: ")
	if len(ts) < 10 {
		t.Errorf("Expected timestamp, got: %s", ts)
	}
}

func TestTemplateEngine_UUID(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("{{uuid()}}")

	// UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
	if len(result) != 36 {
		t.Errorf("Expected 36 char UUID, got %d: %s", len(result), result)
	}

	if result[8] != '-' || result[13] != '-' || result[18] != '-' || result[23] != '-' {
		t.Errorf("Invalid UUID format: %s", result)
	}
}

func TestTemplateEngine_EnvironmentVariable(t *testing.T) {
	os.Setenv("TEST_VAR", "test_value")
	defer os.Unsetenv("TEST_VAR")

	e := NewTemplateEngine(nil)
	result := e.Substitute("{{env(TEST_VAR)}}")

	if result != "test_value" {
		t.Errorf("Expected 'test_value', got '%s'", result)
	}
}

func TestTemplateEngine_EnvWithDefault(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("{{env(NONEXISTENT_VAR, default_val)}}")

	if result != "default_val" {
		t.Errorf("Expected 'default_val', got '%s'", result)
	}
}

func TestTemplateEngine_Upper(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("{{upper(hello)}}")

	if result != "HELLO" {
		t.Errorf("Expected 'HELLO', got '%s'", result)
	}
}

func TestTemplateEngine_Lower(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("{{lower(WORLD)}}")

	if result != "world" {
		t.Errorf("Expected 'world', got '%s'", result)
	}
}

func TestTemplateEngine_Base64(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("{{base64(hello)}}")

	if result != "aGVsbG8=" {
		t.Errorf("Expected 'aGVsbG8=', got '%s'", result)
	}
}

func TestTemplateEngine_URLEncode(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("{{urlencode(hello world)}}")

	if result != "hello%20world" {
		t.Errorf("Expected 'hello%%20world', got '%s'", result)
	}
}

func TestTemplateEngine_Conditional_Exists(t *testing.T) {
	e := NewTemplateEngine(nil)
	e.SetVariable("token", "abc123")

	// Variable exists
	result := e.Substitute("{{?exists:token|has_token|no_token}}")
	if result != "has_token" {
		t.Errorf("Expected 'has_token', got '%s'", result)
	}

	// Variable doesn't exist
	result = e.Substitute("{{?exists:missing|has_val|no_val}}")
	if result != "no_val" {
		t.Errorf("Expected 'no_val', got '%s'", result)
	}
}

func TestTemplateEngine_Conditional_Equality(t *testing.T) {
	e := NewTemplateEngine(nil)
	e.SetVariable("status", "200")

	result := e.Substitute("{{?status==200|success|failure}}")
	if result != "success" {
		t.Errorf("Expected 'success', got '%s'", result)
	}

	result = e.Substitute("{{?status==404|not_found|other}}")
	if result != "other" {
		t.Errorf("Expected 'other', got '%s'", result)
	}
}

func TestTemplateEngine_Conditional_Inequality(t *testing.T) {
	e := NewTemplateEngine(nil)
	e.SetVariable("status", "200")

	result := e.Substitute("{{?status!=200|error|ok}}")
	if result != "ok" {
		t.Errorf("Expected 'ok', got '%s'", result)
	}
}

func TestTemplateEngine_Counter(t *testing.T) {
	e := NewTemplateEngine(nil)

	r1 := e.Substitute("{{counter()}}")
	r2 := e.Substitute("{{counter()}}")
	r3 := e.Substitute("{{counter()}}")

	if r1 == r2 || r2 == r3 {
		t.Error("Counter should increment each call")
	}
}

func TestTemplateEngine_Seq(t *testing.T) {
	e := NewTemplateEngine(nil)
	result := e.Substitute("{{seq(a, b, c)}}")

	if result != "a" && result != "b" && result != "c" {
		t.Errorf("Expected 'a', 'b', or 'c', got '%s'", result)
	}
}

func TestTemplateEngine_ExtractVariables(t *testing.T) {
	e := NewTemplateEngine(nil)
	vars := e.ExtractVariables("Hello {{name}}, your {{item}} is {{status}}")

	if len(vars) != 3 {
		t.Errorf("Expected 3 variables, got %d", len(vars))
	}

	expected := map[string]bool{"name": true, "item": true, "status": true}
	for _, v := range vars {
		if !expected[v] {
			t.Errorf("Unexpected variable: %s", v)
		}
	}
}

func TestTemplateEngine_HasUnresolved(t *testing.T) {
	e := NewTemplateEngine(nil)
	e.SetVariable("name", "Alice")

	// Has unresolved
	if !e.HasUnresolved("Hello {{unknown}}") {
		t.Error("Should have unresolved")
	}

	// Fully resolved (after substitution)
	result := e.Substitute("Hello {{name}}")
	if e.HasUnresolved(result) {
		t.Error("Should not have unresolved after substitution")
	}
}

func TestTemplateEngine_ComplexTemplate(t *testing.T) {
	pool := NewPool(nil)
	defer pool.Close()
	pool.Add("csrf_token", "xyz789")

	e := NewTemplateEngine(pool)
	e.SetVariable("user", "admin")

	template := `{
		"user": "{{user}}",
		"token": "{{csrf_token}}",
		"request_id": "{{uuid()}}",
		"timestamp": {{timestamp()}}
	}`

	result := e.Substitute(template)

	if strings.Contains(result, "{{") {
		t.Errorf("Template not fully substituted: %s", result)
	}

	if !strings.Contains(result, `"user": "admin"`) {
		t.Error("user not substituted")
	}

	if !strings.Contains(result, `"token": "xyz789"`) {
		t.Error("csrf_token not substituted")
	}
}

func TestStateManager_ExtractAndStore(t *testing.T) {
	sm := NewStateManager()
	defer sm.Close()

	sm.AddExtractionRule(&ExtractionRule{
		Name:    "token",
		Type:    ExtractorJSONPath,
		Pattern: "access_token",
	})

	input := &ExtractionInput{
		Body: []byte(`{"access_token": "secret123", "expires": 3600}`),
	}

	results := sm.ExtractAndStore(input)

	if len(results) != 1 {
		t.Errorf("Expected 1 result, got %d", len(results))
	}

	// Token should be in pool
	value, found := sm.Pool().Get("token")
	if !found {
		t.Error("Token should be in pool")
	}
	if value != "secret123" {
		t.Errorf("Expected 'secret123', got '%s'", value)
	}
}

func TestStateManager_Substitute(t *testing.T) {
	sm := NewStateManager()
	defer sm.Close()

	sm.Pool().Add("session_id", "abc123")
	sm.SetVariable("user", "alice")

	result := sm.Substitute("User {{user}} with session {{session_id}}")
	expected := "User alice with session abc123"

	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func TestStateManager_FullFlow(t *testing.T) {
	sm := NewStateManager()
	defer sm.Close()

	// Add extraction rule
	sm.AddExtractionRule(&ExtractionRule{
		Name:    "csrf",
		Type:    ExtractorJSONPath,
		Pattern: "csrf_token",
	})

	// Simulate login response
	loginResponse := &ExtractionInput{
		Body: []byte(`{"csrf_token": "secure_token_123", "user_id": 42}`),
	}
	sm.ExtractAndStore(loginResponse)

	// Now use extracted value in next request
	nextRequest := `{"action": "update", "csrf": "{{csrf}}", "data": {}}`
	result := sm.Substitute(nextRequest)

	expected := `{"action": "update", "csrf": "secure_token_123", "data": {}}`
	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func BenchmarkTemplateEngine_Substitute(b *testing.B) {
	pool := NewPool(nil)
	defer pool.Close()
	pool.Add("token", "abc123")

	e := NewTemplateEngine(pool)
	e.SetVariable("user", "admin")

	template := "User: {{user}}, Token: {{token}}, Time: {{timestamp()}}"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		e.Substitute(template)
	}
}
