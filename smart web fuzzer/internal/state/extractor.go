// Package state provides value extraction from HTTP responses.
// It supports regex patterns, JSON Path, and custom extraction rules
// for extracting dynamic values that can be used in subsequent requests.
package state

import (
	"encoding/json"
	"errors"
	"regexp"
	"strings"

	"github.com/tidwall/gjson"
)

// ExtractorType defines the type of extraction method
type ExtractorType int

const (
	ExtractorRegex ExtractorType = iota
	ExtractorJSONPath
	ExtractorHeader
	ExtractorCookie
	ExtractorXPath
	ExtractorCustom
)

func (t ExtractorType) String() string {
	switch t {
	case ExtractorRegex:
		return "regex"
	case ExtractorJSONPath:
		return "jsonpath"
	case ExtractorHeader:
		return "header"
	case ExtractorCookie:
		return "cookie"
	case ExtractorXPath:
		return "xpath"
	case ExtractorCustom:
		return "custom"
	default:
		return "unknown"
	}
}

// ExtractionRule defines a single extraction rule
type ExtractionRule struct {
	// Name is the identifier for the extracted value
	Name string `json:"name" yaml:"name"`

	// Type is the extraction method type
	Type ExtractorType `json:"type" yaml:"type"`

	// Pattern is the extraction pattern (regex, jsonpath, etc.)
	Pattern string `json:"pattern" yaml:"pattern"`

	// Group is the regex capture group index (for regex type)
	Group int `json:"group,omitempty" yaml:"group,omitempty"`

	// Required indicates if extraction failure should be an error
	Required bool `json:"required,omitempty" yaml:"required,omitempty"`

	// Default is the fallback value if extraction fails
	Default string `json:"default,omitempty" yaml:"default,omitempty"`

	// Transform is an optional transformation function name
	Transform string `json:"transform,omitempty" yaml:"transform,omitempty"`

	// compiled regex (internal use)
	compiledRegex *regexp.Regexp
}

// ExtractionResult contains the result of an extraction attempt
type ExtractionResult struct {
	// Name is the extraction rule name
	Name string

	// Value is the extracted value (empty if not found)
	Value string

	// Found indicates if a value was extracted
	Found bool

	// Error contains any error that occurred
	Error error

	// Source indicates where the value was found
	Source string
}

// Extractor handles value extraction from HTTP responses
type Extractor struct {
	rules      []*ExtractionRule
	transforms map[string]TransformFunc
}

// TransformFunc is a function that transforms extracted values
type TransformFunc func(string) string

// NewExtractor creates a new Extractor
func NewExtractor() *Extractor {
	e := &Extractor{
		rules:      make([]*ExtractionRule, 0),
		transforms: make(map[string]TransformFunc),
	}

	// Register built-in transforms
	e.RegisterTransform("trim", strings.TrimSpace)
	e.RegisterTransform("lower", strings.ToLower)
	e.RegisterTransform("upper", strings.ToUpper)
	e.RegisterTransform("urldecode", urlDecode)
	e.RegisterTransform("htmlunescape", htmlUnescape)

	return e
}

// AddRule adds an extraction rule
func (e *Extractor) AddRule(rule *ExtractionRule) error {
	// Compile regex if needed
	if rule.Type == ExtractorRegex && rule.Pattern != "" {
		re, err := regexp.Compile(rule.Pattern)
		if err != nil {
			return err
		}
		rule.compiledRegex = re
	}

	e.rules = append(e.rules, rule)
	return nil
}

// AddRules adds multiple extraction rules
func (e *Extractor) AddRules(rules []*ExtractionRule) error {
	for _, rule := range rules {
		if err := e.AddRule(rule); err != nil {
			return err
		}
	}
	return nil
}

// RegisterTransform registers a custom transform function
func (e *Extractor) RegisterTransform(name string, fn TransformFunc) {
	e.transforms[name] = fn
}

// ExtractionInput contains the data to extract from
type ExtractionInput struct {
	Body        []byte
	Headers     map[string]string
	Cookies     map[string]string
	StatusCode  int
	ContentType string
}

// Extract extracts values from the input using all configured rules
func (e *Extractor) Extract(input *ExtractionInput) []ExtractionResult {
	results := make([]ExtractionResult, 0, len(e.rules))

	for _, rule := range e.rules {
		result := e.extractSingle(input, rule)
		results = append(results, result)
	}

	return results
}

// ExtractToMap extracts values and returns them as a map
func (e *Extractor) ExtractToMap(input *ExtractionInput) (map[string]string, error) {
	results := e.Extract(input)
	values := make(map[string]string)
	var errs []string

	for _, result := range results {
		if result.Found {
			values[result.Name] = result.Value
		} else if result.Error != nil {
			errs = append(errs, result.Name+": "+result.Error.Error())
		}
	}

	if len(errs) > 0 {
		return values, errors.New("extraction errors: " + strings.Join(errs, "; "))
	}

	return values, nil
}

// extractSingle extracts a single value using the given rule
func (e *Extractor) extractSingle(input *ExtractionInput, rule *ExtractionRule) ExtractionResult {
	result := ExtractionResult{
		Name: rule.Name,
	}

	var value string
	var found bool

	switch rule.Type {
	case ExtractorRegex:
		value, found = e.extractRegex(input.Body, rule)
		result.Source = "body"

	case ExtractorJSONPath:
		value, found = e.extractJSONPath(input.Body, rule.Pattern)
		result.Source = "body"

	case ExtractorHeader:
		value, found = e.extractHeader(input.Headers, rule.Pattern)
		result.Source = "header"

	case ExtractorCookie:
		value, found = e.extractCookie(input.Cookies, rule.Pattern)
		result.Source = "cookie"

	case ExtractorCustom:
		value, found = e.extractCustom(input, rule)
		result.Source = "custom"

	default:
		result.Error = errors.New("unknown extractor type")
		return result
	}

	if found {
		result.Found = true
		result.Value = e.applyTransform(value, rule.Transform)
	} else if rule.Default != "" {
		result.Found = true
		result.Value = rule.Default
	} else if rule.Required {
		result.Error = errors.New("required value not found")
	}

	return result
}

// extractRegex extracts a value using regex
func (e *Extractor) extractRegex(body []byte, rule *ExtractionRule) (string, bool) {
	if rule.compiledRegex == nil {
		return "", false
	}

	matches := rule.compiledRegex.FindSubmatch(body)
	if matches == nil {
		return "", false
	}

	// Get the specified group or the first capture group
	group := rule.Group
	if group >= len(matches) {
		group = 0
	}
	if group == 0 && len(matches) > 1 {
		group = 1 // Default to first capture group
	}

	return string(matches[group]), true
}

// extractJSONPath extracts a value using JSON Path
func (e *Extractor) extractJSONPath(body []byte, path string) (string, bool) {
	// Check if body is valid JSON
	if !json.Valid(body) {
		return "", false
	}

	result := gjson.GetBytes(body, path)
	if !result.Exists() {
		return "", false
	}

	return result.String(), true
}

// extractHeader extracts a value from headers
func (e *Extractor) extractHeader(headers map[string]string, name string) (string, bool) {
	// Case-insensitive header lookup
	lowerName := strings.ToLower(name)
	for key, value := range headers {
		if strings.ToLower(key) == lowerName {
			return value, true
		}
	}
	return "", false
}

// extractCookie extracts a value from cookies
func (e *Extractor) extractCookie(cookies map[string]string, name string) (string, bool) {
	if value, exists := cookies[name]; exists {
		return value, true
	}
	return "", false
}

// extractCustom handles custom extraction logic
func (e *Extractor) extractCustom(input *ExtractionInput, rule *ExtractionRule) (string, bool) {
	// Custom extraction patterns
	switch rule.Pattern {
	case "status_code":
		return string(rune('0'+input.StatusCode/100)) +
			string(rune('0'+(input.StatusCode/10)%10)) +
			string(rune('0'+input.StatusCode%10)), true

	case "content_type":
		return input.ContentType, input.ContentType != ""

	case "body_length":
		return intToString(len(input.Body)), true

	default:
		// Try as regex on body
		if re, err := regexp.Compile(rule.Pattern); err == nil {
			if m := re.FindSubmatch(input.Body); m != nil {
				if len(m) > 1 {
					return string(m[1]), true
				}
				return string(m[0]), true
			}
		}
		return "", false
	}
}

// applyTransform applies a transform function if specified
func (e *Extractor) applyTransform(value, transformName string) string {
	if transformName == "" {
		return value
	}

	if fn, exists := e.transforms[transformName]; exists {
		return fn(value)
	}

	return value
}

// --- Helper functions ---

func intToString(n int) string {
	if n == 0 {
		return "0"
	}

	var result []byte
	negative := n < 0
	if negative {
		n = -n
	}

	for n > 0 {
		result = append([]byte{byte('0' + n%10)}, result...)
		n /= 10
	}

	if negative {
		result = append([]byte{'-'}, result...)
	}

	return string(result)
}

func urlDecode(s string) string {
	var result strings.Builder
	result.Grow(len(s))

	for i := 0; i < len(s); i++ {
		if s[i] == '%' && i+2 < len(s) {
			if h := hexToByte(s[i+1], s[i+2]); h >= 0 {
				result.WriteByte(byte(h))
				i += 2
				continue
			}
		} else if s[i] == '+' {
			result.WriteByte(' ')
			continue
		}
		result.WriteByte(s[i])
	}

	return result.String()
}

func hexToByte(h1, h2 byte) int {
	d1 := hexDigit(h1)
	d2 := hexDigit(h2)
	if d1 < 0 || d2 < 0 {
		return -1
	}
	return d1*16 + d2
}

func hexDigit(b byte) int {
	switch {
	case b >= '0' && b <= '9':
		return int(b - '0')
	case b >= 'a' && b <= 'f':
		return int(b - 'a' + 10)
	case b >= 'A' && b <= 'F':
		return int(b - 'A' + 10)
	}
	return -1
}

func htmlUnescape(s string) string {
	replacer := strings.NewReplacer(
		"&amp;", "&",
		"&lt;", "<",
		"&gt;", ">",
		"&quot;", "\"",
		"&#39;", "'",
		"&apos;", "'",
	)
	return replacer.Replace(s)
}

// --- Preset Rules ---

// CSRFTokenRule creates a rule for extracting CSRF tokens
func CSRFTokenRule() *ExtractionRule {
	return &ExtractionRule{
		Name:    "csrf_token",
		Type:    ExtractorRegex,
		Pattern: `(?:csrf[_-]?token|_token|authenticity_token)["\s]*[=:]\s*["']?([^"'\s<>]+)["']?`,
		Group:   1,
	}
}

// SessionIDRule creates a rule for extracting session IDs
func SessionIDRule() *ExtractionRule {
	return &ExtractionRule{
		Name:    "session_id",
		Type:    ExtractorCookie,
		Pattern: "PHPSESSID",
	}
}

// BearerTokenRule creates a rule for extracting bearer tokens from JSON
func BearerTokenRule() *ExtractionRule {
	return &ExtractionRule{
		Name:    "access_token",
		Type:    ExtractorJSONPath,
		Pattern: "access_token",
	}
}

// RedirectLocationRule creates a rule for extracting redirect location
func RedirectLocationRule() *ExtractionRule {
	return &ExtractionRule{
		Name:    "redirect_location",
		Type:    ExtractorHeader,
		Pattern: "Location",
	}
}
