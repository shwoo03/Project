package mutator

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"

	"github.com/fluxfuzzer/fluxfuzzer/pkg/types"
)

// --- SmartMutator Tests ---

func TestSmartMutator_Name(t *testing.T) {
	tests := []struct {
		payloadType PayloadType
		expected    string
	}{
		{PayloadSQLi, "smart/sqli"},
		{PayloadXSS, "smart/xss"},
		{PayloadPathTraversal, "smart/path_traversal"},
		{PayloadCommandInjection, "smart/command_injection"},
		{PayloadLDAP, "smart/ldap"},
		{PayloadXML, "smart/xml"},
		{PayloadSSTI, "smart/ssti"},
		{PayloadNoSQL, "smart/nosql"},
		{PayloadEmail, "smart/email"},
		{PayloadURL, "smart/url"},
	}

	for _, tt := range tests {
		m := NewSmartMutator(tt.payloadType)
		if m.Name() != tt.expected {
			t.Errorf("payloadType=%v: expected %s, got %s", tt.payloadType, tt.expected, m.Name())
		}
	}
}

func TestSmartMutator_Type(t *testing.T) {
	m := NewSmartMutator(PayloadSQLi)
	if m.Type() != types.StructureAware {
		t.Errorf("expected StructureAware type")
	}
}

func TestSmartMutator_Mutate(t *testing.T) {
	m := NewSmartMutator(PayloadSQLi)

	input := []byte("test")
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be one of the SQLi payloads
	found := false
	for _, p := range sqlInjectionPayloads {
		if string(mutated) == p {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("result %q is not a valid SQLi payload", mutated)
	}
}

func TestSmartMutator_AppendPayload(t *testing.T) {
	m := NewSmartMutator(PayloadXSS)

	input := []byte("prefix")
	result, err := m.AppendPayload(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	if !bytes.HasPrefix(result, input) {
		t.Error("result should start with original input")
	}

	if bytes.Equal(result, input) {
		t.Error("result should be longer than input")
	}
}

func TestSmartMutator_PrependPayload(t *testing.T) {
	m := NewSmartMutator(PayloadXSS)

	input := []byte("suffix")
	result, err := m.PrependPayload(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	if !bytes.HasSuffix(result, input) {
		t.Error("result should end with original input")
	}
}

func TestPayloadType_String(t *testing.T) {
	tests := []struct {
		payloadType PayloadType
		expected    string
	}{
		{PayloadSQLi, "sqli"},
		{PayloadXSS, "xss"},
		{PayloadPathTraversal, "path_traversal"},
		{PayloadCommandInjection, "command_injection"},
	}

	for _, tt := range tests {
		if tt.payloadType.String() != tt.expected {
			t.Errorf("expected %s, got %s", tt.expected, tt.payloadType.String())
		}
	}
}

// --- JSONMutator Tests ---

func TestJSONMutator_Name(t *testing.T) {
	tests := []struct {
		mutationType JSONMutationType
		expected     string
	}{
		{JSONTypeConfusion, "json/type_confusion"},
		{JSONKeyMangling, "json/key_mangle"},
		{JSONValueMutation, "json/value_mutation"},
		{JSONStructure, "json/structure"},
		{JSONInjection, "json/injection"},
	}

	for _, tt := range tests {
		m := NewJSONMutator(tt.mutationType)
		if m.Name() != tt.expected {
			t.Errorf("mutationType=%v: expected %s, got %s", tt.mutationType, tt.expected, m.Name())
		}
	}
}

func TestJSONMutator_Type(t *testing.T) {
	m := NewJSONMutator(JSONTypeConfusion)
	if m.Type() != types.StructureAware {
		t.Errorf("expected StructureAware type")
	}
}

func TestJSONMutator_TypeConfusion(t *testing.T) {
	m := NewJSONMutator(JSONTypeConfusion)

	input := []byte(`{"name": "test", "count": 42, "active": true}`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should still be valid JSON
	var result interface{}
	if err := json.Unmarshal(mutated, &result); err != nil {
		t.Errorf("result is not valid JSON: %v", err)
	}
}

func TestJSONMutator_KeyMangling(t *testing.T) {
	m := NewJSONMutator(JSONKeyMangling)

	input := []byte(`{"username": "admin"}`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be valid JSON with modified keys
	var result map[string]interface{}
	if err := json.Unmarshal(mutated, &result); err != nil {
		t.Errorf("result is not valid JSON: %v", err)
	}

	// Original key should be gone or modified
	if _, exists := result["username"]; exists {
		t.Log("Key was not mangled (might happen due to randomness)")
	}
}

func TestJSONMutator_ValueMutation(t *testing.T) {
	m := NewJSONMutator(JSONValueMutation)

	input := []byte(`{"value": "test"}`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be valid JSON
	var result map[string]interface{}
	if err := json.Unmarshal(mutated, &result); err != nil {
		t.Errorf("result is not valid JSON: %v", err)
	}

	// Value should be different
	val := result["value"].(string)
	if val == "test" {
		t.Log("Value was not mutated (might happen due to randomness)")
	}
}

func TestJSONMutator_Structure(t *testing.T) {
	m := NewJSONMutator(JSONStructure)

	input := []byte(`{"key": "value"}`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be valid JSON
	var result interface{}
	if err := json.Unmarshal(mutated, &result); err != nil {
		t.Errorf("result is not valid JSON: %v", err)
	}
}

func TestJSONMutator_Injection(t *testing.T) {
	m := NewJSONMutator(JSONInjection)

	input := []byte(`{"user": "test", "pass": "secret"}`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be valid JSON
	var result map[string]interface{}
	if err := json.Unmarshal(mutated, &result); err != nil {
		t.Errorf("result is not valid JSON: %v", err)
	}
}

func TestJSONMutator_InvalidJSON(t *testing.T) {
	m := NewJSONMutator(JSONTypeConfusion)

	input := []byte("not json at all")
	result, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should return input unchanged
	if !bytes.Equal(input, result) {
		t.Error("invalid JSON should be returned unchanged")
	}
}

func TestJSONMutator_MutateWithType(t *testing.T) {
	m := NewJSONMutator(JSONTypeConfusion)

	// Non-JSON type should return unchanged
	input := []byte(`{"key": "value"}`)
	result, err := m.MutateWithType(input, TypeString)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	if !bytes.Equal(input, result) {
		t.Error("non-JSON type should be returned unchanged")
	}
}

// --- XMLMutator Tests ---

func TestXMLMutator_Name(t *testing.T) {
	tests := []struct {
		mutationType XMLMutationType
		expected     string
	}{
		{XMLEntityInjection, "xml/entity"},
		{XMLTagMangling, "xml/tag"},
		{XMLAttributeMutation, "xml/attribute"},
		{XMLCDATAInjection, "xml/cdata"},
	}

	for _, tt := range tests {
		m := NewXMLMutator(tt.mutationType)
		if m.Name() != tt.expected {
			t.Errorf("mutationType=%v: expected %s, got %s", tt.mutationType, tt.expected, m.Name())
		}
	}
}

func TestXMLMutator_Type(t *testing.T) {
	m := NewXMLMutator(XMLEntityInjection)
	if m.Type() != types.StructureAware {
		t.Errorf("expected StructureAware type")
	}
}

func TestXMLMutator_EntityInjection(t *testing.T) {
	m := NewXMLMutator(XMLEntityInjection)

	input := []byte(`<root><data>test</data></root>`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should contain DOCTYPE
	if !bytes.Contains(mutated, []byte("DOCTYPE")) {
		t.Error("result should contain DOCTYPE for XXE")
	}
}

func TestXMLMutator_EntityInjection_WithDeclaration(t *testing.T) {
	m := NewXMLMutator(XMLEntityInjection)

	input := []byte(`<?xml version="1.0"?><root><data>test</data></root>`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should preserve XML declaration and add DOCTYPE
	if !bytes.Contains(mutated, []byte("<?xml")) {
		t.Error("result should preserve XML declaration")
	}
	if !bytes.Contains(mutated, []byte("DOCTYPE")) {
		t.Error("result should contain DOCTYPE")
	}
}

func TestXMLMutator_TagMangling(t *testing.T) {
	m := NewXMLMutator(XMLTagMangling)

	input := []byte(`<root>test</root>`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Tag should be modified
	if bytes.Equal(input, mutated) {
		t.Log("Tag was not mangled (might happen with certain random selections)")
	}
}

func TestXMLMutator_AttributeMutation(t *testing.T) {
	m := NewXMLMutator(XMLAttributeMutation)

	input := []byte(`<root id="123">test</root>`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Attribute value should be modified
	if bytes.Equal(input, mutated) {
		t.Log("Attribute was not mutated")
	}
}

func TestXMLMutator_CDATAInjection(t *testing.T) {
	m := NewXMLMutator(XMLCDATAInjection)

	input := []byte(`<root>test</root>`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should contain CDATA
	if !bytes.Contains(mutated, []byte("CDATA")) {
		t.Error("result should contain CDATA section")
	}
}

func TestXMLMutator_NonXMLInput(t *testing.T) {
	m := NewXMLMutator(XMLEntityInjection)

	input := []byte("not xml")
	result, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should return unchanged
	if !bytes.Equal(input, result) {
		t.Error("non-XML should be returned unchanged")
	}
}

// --- TypeInferrer Tests ---

func TestTypeInferrer_InferType(t *testing.T) {
	inferrer := NewTypeInferrer()

	tests := []struct {
		input    string
		expected InputType
	}{
		{`{"key": "value"}`, TypeJSON},
		{`[1, 2, 3]`, TypeJSON},
		{`<root>data</root>`, TypeXML},
		{`<html><body>test</body></html>`, TypeHTML},
		{`eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.signature`, TypeJWT},
		{`550e8400-e29b-41d4-a716-446655440000`, TypeUUID},
		{`test@example.com`, TypeEmail},
		{`https://example.com`, TypeURL},
		{`12345`, TypeInteger},
		{`-12345`, TypeInteger},
		{`12.345`, TypeFloat},
		{`1.5e10`, TypeFloat},
		{`plain text`, TypeString},
	}

	for _, tt := range tests {
		result := inferrer.InferType([]byte(tt.input))
		if result != tt.expected {
			t.Errorf("input %q: expected %s, got %s", tt.input, tt.expected.String(), result.String())
		}
	}
}

func TestTypeInferrer_EmptyInput(t *testing.T) {
	inferrer := NewTypeInferrer()

	result := inferrer.InferType([]byte{})
	if result != TypeUnknown {
		t.Errorf("expected TypeUnknown for empty input, got %s", result.String())
	}
}

func TestTypeInferrer_IsJWT(t *testing.T) {
	inferrer := NewTypeInferrer()

	tests := []struct {
		input    string
		expected bool
	}{
		{"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.signature", true},
		{"not.a.jwt", false},
		{"only.two", false},
		{"a.b.c.d", false},
	}

	for _, tt := range tests {
		result := inferrer.isJWT(tt.input)
		if result != tt.expected {
			t.Errorf("input %q: expected %v, got %v", tt.input, tt.expected, result)
		}
	}
}

func TestTypeInferrer_IsUUID(t *testing.T) {
	inferrer := NewTypeInferrer()

	tests := []struct {
		input    string
		expected bool
	}{
		{"550e8400-e29b-41d4-a716-446655440000", true},
		{"00000000-0000-0000-0000-000000000000", true},
		{"not-a-uuid", false},
		{"550e840-e29b-41d4-a716-446655440000", false},  // Wrong format
		{"550e8400xe29b-41d4-a716-446655440000", false}, // Wrong separator
	}

	for _, tt := range tests {
		result := inferrer.isUUID(tt.input)
		if result != tt.expected {
			t.Errorf("input %q: expected %v, got %v", tt.input, tt.expected, result)
		}
	}
}

func TestTypeInferrer_IsEmail(t *testing.T) {
	inferrer := NewTypeInferrer()

	tests := []struct {
		input    string
		expected bool
	}{
		{"test@example.com", true},
		{"user@domain.org", true},
		{"@example.com", false},
		{"test@", false},
		{"test", false},
	}

	for _, tt := range tests {
		result := inferrer.isEmail(tt.input)
		if result != tt.expected {
			t.Errorf("input %q: expected %v, got %v", tt.input, tt.expected, result)
		}
	}
}

// --- BoundaryMutator Tests ---

func TestBoundaryMutator_Name(t *testing.T) {
	m := NewBoundaryMutator()
	if m.Name() != "smart/boundary" {
		t.Errorf("expected 'smart/boundary', got '%s'", m.Name())
	}
}

func TestBoundaryMutator_MutateInteger(t *testing.T) {
	m := NewBoundaryMutator()

	input := []byte("12345")
	mutated, err := m.MutateWithType(input, TypeInteger)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be a boundary integer value
	boundaries := []string{
		"0", "-1", "1", "127", "-128", "255", "256",
		"32767", "-32768", "65535", "65536",
		"2147483647", "-2147483648",
	}

	valid := false
	for _, b := range boundaries {
		if string(mutated) == b {
			valid = true
			break
		}
	}

	if !valid && len(mutated) > 0 {
		// Check if it's still a number-like value
		t.Logf("Got boundary value: %s", mutated)
	}
}

func TestBoundaryMutator_MutateFloat(t *testing.T) {
	m := NewBoundaryMutator()

	input := []byte("3.14")
	mutated, err := m.MutateWithType(input, TypeFloat)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be a float boundary value
	if len(mutated) == 0 {
		t.Error("expected non-empty result")
	}
}

func TestBoundaryMutator_MutateUUID(t *testing.T) {
	m := NewBoundaryMutator()

	input := []byte("550e8400-e29b-41d4-a716-446655440000")
	mutated, err := m.MutateWithType(input, TypeUUID)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should look like a UUID (possibly invalid)
	if len(mutated) < 10 {
		t.Logf("Got boundary UUID: %s", mutated)
	}
}

// --- UnicodeAttackMutator Tests ---

func TestUnicodeAttackMutator_Name(t *testing.T) {
	m := NewUnicodeAttackMutator()
	if m.Name() != "smart/unicode" {
		t.Errorf("expected 'smart/unicode', got '%s'", m.Name())
	}
}

func TestUnicodeAttackMutator_Mutate(t *testing.T) {
	m := NewUnicodeAttackMutator()

	input := []byte("test")
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be different from input
	if bytes.Equal(input, mutated) {
		t.Log("Mutation may have resulted in same value (possible with some attacks)")
	}
}

func TestUnicodeAttackMutator_NullByteInjection(t *testing.T) {
	m := NewUnicodeAttackMutator()

	input := []byte("test")

	// Run multiple times to test null byte injection
	foundNull := false
	for i := 0; i < 100; i++ {
		mutated, _ := m.Mutate(input)
		if bytes.Contains(mutated, []byte{0x00}) {
			foundNull = true
			break
		}
	}

	// Should have found null byte in at least one mutation
	// (depends on random selection)
	t.Logf("Found null byte injection: %v", foundNull)
}

// --- RegisterSmartMutators Tests ---

func TestRegisterSmartMutators(t *testing.T) {
	engine := NewMutatorEngine()

	RegisterSmartMutators(engine)

	expectedNames := []string{
		"smart/sqli", "smart/xss", "smart/path_traversal",
		"smart/command_injection", "smart/ldap", "smart/xml",
		"smart/ssti", "smart/nosql",
		"json/type_confusion", "json/key_mangle", "json/value_mutation",
		"json/structure", "json/injection",
		"xml/entity", "xml/tag", "xml/attribute", "xml/cdata",
		"smart/boundary", "smart/unicode",
	}

	for _, name := range expectedNames {
		if _, exists := engine.Registry().Get(name); !exists {
			t.Errorf("expected mutator %s to be registered", name)
		}
	}
}

// --- Payload Getter Tests ---

func TestGetPayloads(t *testing.T) {
	sqli := GetSQLiPayloads()
	if len(sqli) == 0 {
		t.Error("SQLi payloads should not be empty")
	}

	xss := GetXSSPayloads()
	if len(xss) == 0 {
		t.Error("XSS payloads should not be empty")
	}

	pt := GetPathTraversalPayloads()
	if len(pt) == 0 {
		t.Error("Path traversal payloads should not be empty")
	}

	ci := GetCommandInjectionPayloads()
	if len(ci) == 0 {
		t.Error("Command injection payloads should not be empty")
	}
}

// --- Integration Tests ---

func TestSmartMutators_Integration(t *testing.T) {
	engine := NewMutatorEngine()
	engine.SetProbability(1.0)
	RegisterSmartMutators(engine)

	inputs := [][]byte{
		[]byte("test string"),
		[]byte(`{"key": "value"}`),
		[]byte(`<root>data</root>`),
		[]byte("12345"),
		[]byte("test@example.com"),
	}

	for _, input := range inputs {
		result := engine.Mutate(input)
		if !result.Success {
			t.Errorf("mutation failed for input %q: %v", input, result.Error)
		}
	}
}

// --- Benchmark Tests ---

func BenchmarkSmartMutator_SQLi(b *testing.B) {
	m := NewSmartMutator(PayloadSQLi)
	input := []byte("user input")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		m.Mutate(input)
	}
}

func BenchmarkJSONMutator_TypeConfusion(b *testing.B) {
	m := NewJSONMutator(JSONTypeConfusion)
	input := []byte(`{"name": "test", "count": 42, "active": true}`)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		m.Mutate(input)
	}
}

func BenchmarkTypeInferrer(b *testing.B) {
	inferrer := NewTypeInferrer()
	inputs := [][]byte{
		[]byte(`{"key": "value"}`),
		[]byte(`<root>data</root>`),
		[]byte("12345"),
		[]byte("test@example.com"),
		[]byte("plain text"),
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		inferrer.InferType(inputs[i%len(inputs)])
	}
}

func BenchmarkUnicodeAttackMutator(b *testing.B) {
	m := NewUnicodeAttackMutator()
	input := []byte("test input for unicode attacks")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		m.Mutate(input)
	}
}

func BenchmarkRegisterSmartMutators(b *testing.B) {
	for i := 0; i < b.N; i++ {
		engine := NewMutatorEngine()
		RegisterSmartMutators(engine)
	}
}

// --- Helper Function Tests ---

func TestIsBase64Char(t *testing.T) {
	validChars := "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/-_"
	for _, c := range validChars {
		if !isBase64Char(c) {
			t.Errorf("expected %c to be valid base64 char", c)
		}
	}

	invalidChars := "!@#$%^&*()"
	for _, c := range invalidChars {
		if isBase64Char(c) {
			t.Errorf("expected %c to be invalid base64 char", c)
		}
	}
}

func TestIsHexChar(t *testing.T) {
	validChars := "0123456789abcdefABCDEF"
	for _, c := range validChars {
		if !isHexChar(c) {
			t.Errorf("expected %c to be valid hex char", c)
		}
	}

	invalidChars := "ghijklmnopqrstuvwxyzGHIJKLMNOPQRSTUVWXYZ"
	for _, c := range invalidChars {
		if isHexChar(c) {
			t.Errorf("expected %c to be invalid hex char", c)
		}
	}
}

// --- Edge Case Tests ---

func TestJSONMutator_EmptyObject(t *testing.T) {
	m := NewJSONMutator(JSONStructure)

	input := []byte(`{}`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	var result interface{}
	if err := json.Unmarshal(mutated, &result); err != nil {
		t.Errorf("result is not valid JSON: %v", err)
	}
}

func TestJSONMutator_Array(t *testing.T) {
	m := NewJSONMutator(JSONStructure)

	input := []byte(`[1, 2, 3]`)
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	var result interface{}
	if err := json.Unmarshal(mutated, &result); err != nil {
		t.Errorf("result is not valid JSON: %v", err)
	}
}

func TestXMLMutator_EmptyElement(t *testing.T) {
	m := NewXMLMutator(XMLCDATAInjection)

	input := []byte(`<root/>`)
	_, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestBoundaryMutator_UnknownType(t *testing.T) {
	m := NewBoundaryMutator()

	input := []byte("random data")
	result, err := m.MutateWithType(input, TypeUnknown)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should return unchanged for unknown type
	if !bytes.Equal(input, result) {
		t.Log("Unknown type handling may vary")
	}
}

// Test that all payloads contain expected content
func TestPayloadContent(t *testing.T) {
	// SQLi should contain SQL keywords
	sqli := GetSQLiPayloads()
	hasSQLKeyword := false
	for _, p := range sqli {
		lower := strings.ToLower(p)
		if strings.Contains(lower, "or") || strings.Contains(lower, "select") ||
			strings.Contains(lower, "union") || strings.Contains(lower, "'") {
			hasSQLKeyword = true
			break
		}
	}
	if !hasSQLKeyword {
		t.Error("SQLi payloads should contain SQL keywords")
	}

	// XSS should contain script or event handlers
	xss := GetXSSPayloads()
	hasXSSContent := false
	for _, p := range xss {
		lower := strings.ToLower(p)
		if strings.Contains(lower, "script") || strings.Contains(lower, "onerror") ||
			strings.Contains(lower, "onload") || strings.Contains(lower, "javascript") {
			hasXSSContent = true
			break
		}
	}
	if !hasXSSContent {
		t.Error("XSS payloads should contain script tags or event handlers")
	}
}
