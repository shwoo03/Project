package state

import (
	"testing"
)

func TestExtractor_RegexExtraction(t *testing.T) {
	e := NewExtractor()

	err := e.AddRule(&ExtractionRule{
		Name:    "user_id",
		Type:    ExtractorRegex,
		Pattern: `user_id["\s]*[:=]\s*["']?(\d+)`,
		Group:   1,
	})
	if err != nil {
		t.Fatalf("Failed to add rule: %v", err)
	}

	input := &ExtractionInput{
		Body: []byte(`{"user_id": "12345", "name": "test"}`),
	}

	results := e.Extract(input)

	if len(results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(results))
	}

	if !results[0].Found {
		t.Error("Expected value to be found")
	}

	if results[0].Value != "12345" {
		t.Errorf("Expected '12345', got '%s'", results[0].Value)
	}
}

func TestExtractor_JSONPathExtraction(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:    "user_name",
		Type:    ExtractorJSONPath,
		Pattern: "data.user.name",
	})

	input := &ExtractionInput{
		Body: []byte(`{"data": {"user": {"name": "John Doe", "id": 123}}}`),
	}

	results := e.Extract(input)

	if !results[0].Found {
		t.Error("Expected value to be found")
	}

	if results[0].Value != "John Doe" {
		t.Errorf("Expected 'John Doe', got '%s'", results[0].Value)
	}
}

func TestExtractor_JSONPathArray(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:    "first_item",
		Type:    ExtractorJSONPath,
		Pattern: "items.0.id",
	})

	input := &ExtractionInput{
		Body: []byte(`{"items": [{"id": "abc123"}, {"id": "def456"}]}`),
	}

	results := e.Extract(input)

	if !results[0].Found {
		t.Error("Expected value to be found")
	}

	if results[0].Value != "abc123" {
		t.Errorf("Expected 'abc123', got '%s'", results[0].Value)
	}
}

func TestExtractor_HeaderExtraction(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:    "auth_token",
		Type:    ExtractorHeader,
		Pattern: "Authorization",
	})

	input := &ExtractionInput{
		Headers: map[string]string{
			"Authorization": "Bearer abc123xyz",
			"Content-Type":  "application/json",
		},
	}

	results := e.Extract(input)

	if !results[0].Found {
		t.Error("Expected value to be found")
	}

	if results[0].Value != "Bearer abc123xyz" {
		t.Errorf("Expected 'Bearer abc123xyz', got '%s'", results[0].Value)
	}
}

func TestExtractor_CookieExtraction(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:    "session",
		Type:    ExtractorCookie,
		Pattern: "PHPSESSID",
	})

	input := &ExtractionInput{
		Cookies: map[string]string{
			"PHPSESSID": "abc123session",
			"user_pref": "dark_mode",
		},
	}

	results := e.Extract(input)

	if !results[0].Found {
		t.Error("Expected value to be found")
	}

	if results[0].Value != "abc123session" {
		t.Errorf("Expected 'abc123session', got '%s'", results[0].Value)
	}
}

func TestExtractor_DefaultValue(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:    "missing_value",
		Type:    ExtractorJSONPath,
		Pattern: "nonexistent.path",
		Default: "default_value",
	})

	input := &ExtractionInput{
		Body: []byte(`{"other": "data"}`),
	}

	results := e.Extract(input)

	if !results[0].Found {
		t.Error("Expected Found to be true when default is used")
	}

	if results[0].Value != "default_value" {
		t.Errorf("Expected 'default_value', got '%s'", results[0].Value)
	}
}

func TestExtractor_RequiredValue(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:     "required_value",
		Type:     ExtractorJSONPath,
		Pattern:  "nonexistent.path",
		Required: true,
	})

	input := &ExtractionInput{
		Body: []byte(`{"other": "data"}`),
	}

	results := e.Extract(input)

	if results[0].Found {
		t.Error("Expected Found to be false")
	}

	if results[0].Error == nil {
		t.Error("Expected error for required missing value")
	}
}

func TestExtractor_Transform(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:      "upper_value",
		Type:      ExtractorJSONPath,
		Pattern:   "name",
		Transform: "upper",
	})

	e.AddRule(&ExtractionRule{
		Name:      "lower_value",
		Type:      ExtractorJSONPath,
		Pattern:   "name",
		Transform: "lower",
	})

	input := &ExtractionInput{
		Body: []byte(`{"name": "Hello World"}`),
	}

	results := e.Extract(input)

	if results[0].Value != "HELLO WORLD" {
		t.Errorf("Expected 'HELLO WORLD', got '%s'", results[0].Value)
	}

	if results[1].Value != "hello world" {
		t.Errorf("Expected 'hello world', got '%s'", results[1].Value)
	}
}

func TestExtractor_ExtractToMap(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:    "id",
		Type:    ExtractorJSONPath,
		Pattern: "user.id",
	})

	e.AddRule(&ExtractionRule{
		Name:    "name",
		Type:    ExtractorJSONPath,
		Pattern: "user.name",
	})

	input := &ExtractionInput{
		Body: []byte(`{"user": {"id": "123", "name": "Alice"}}`),
	}

	values, err := e.ExtractToMap(input)
	if err != nil {
		t.Errorf("Unexpected error: %v", err)
	}

	if values["id"] != "123" {
		t.Errorf("Expected id='123', got '%s'", values["id"])
	}

	if values["name"] != "Alice" {
		t.Errorf("Expected name='Alice', got '%s'", values["name"])
	}
}

func TestExtractor_CSRFToken(t *testing.T) {
	e := NewExtractor()
	e.AddRule(CSRFTokenRule())

	tests := []struct {
		name     string
		body     string
		expected string
	}{
		{
			name:     "json format with csrf_token",
			body:     `{"csrf_token": "abc123xyz", "data": {}}`,
			expected: "abc123xyz",
		},
		{
			name:     "json format with _token",
			body:     `{"_token": "def456", "data": {}}`,
			expected: "def456",
		},
		{
			name:     "key value format",
			body:     `csrf_token = "ghi789"`,
			expected: "ghi789",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			input := &ExtractionInput{Body: []byte(tt.body)}
			results := e.Extract(input)

			if !results[0].Found {
				t.Errorf("Expected CSRF token to be found")
				return
			}

			if results[0].Value != tt.expected {
				t.Errorf("Expected '%s', got '%s'", tt.expected, results[0].Value)
			}
		})
	}
}

func TestExtractor_CustomExtraction(t *testing.T) {
	e := NewExtractor()

	e.AddRule(&ExtractionRule{
		Name:    "status",
		Type:    ExtractorCustom,
		Pattern: "status_code",
	})

	e.AddRule(&ExtractionRule{
		Name:    "length",
		Type:    ExtractorCustom,
		Pattern: "body_length",
	})

	input := &ExtractionInput{
		StatusCode: 200,
		Body:       []byte("Hello World"),
	}

	results := e.Extract(input)

	if results[0].Value != "200" {
		t.Errorf("Expected '200', got '%s'", results[0].Value)
	}

	if results[1].Value != "11" {
		t.Errorf("Expected '11', got '%s'", results[1].Value)
	}
}

func TestURLDecode(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"hello%20world", "hello world"},
		{"test%2B123", "test+123"},
		{"foo+bar", "foo bar"},
		{"no%encoding", "no%encoding"},
		{"%3Cscript%3E", "<script>"},
	}

	for _, tt := range tests {
		result := urlDecode(tt.input)
		if result != tt.expected {
			t.Errorf("urlDecode(%s): expected '%s', got '%s'", tt.input, tt.expected, result)
		}
	}
}

func TestHtmlUnescape(t *testing.T) {
	input := "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;"
	expected := `<script>alert("xss")</script>`

	result := htmlUnescape(input)
	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func BenchmarkExtractor_Regex(b *testing.B) {
	e := NewExtractor()
	e.AddRule(&ExtractionRule{
		Name:    "token",
		Type:    ExtractorRegex,
		Pattern: `token["\s]*[:=]\s*["']?([^"'\s]+)`,
		Group:   1,
	})

	input := &ExtractionInput{
		Body: []byte(`{"token": "abc123xyz789", "user": {"id": 1}}`),
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		e.Extract(input)
	}
}

func BenchmarkExtractor_JSONPath(b *testing.B) {
	e := NewExtractor()
	e.AddRule(&ExtractionRule{
		Name:    "token",
		Type:    ExtractorJSONPath,
		Pattern: "data.token",
	})

	input := &ExtractionInput{
		Body: []byte(`{"data": {"token": "abc123xyz789", "user": {"id": 1}}}`),
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		e.Extract(input)
	}
}
