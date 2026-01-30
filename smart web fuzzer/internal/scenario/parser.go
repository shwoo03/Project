// Package scenario provides YAML parsing for scenario definitions.
package scenario

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// Parser handles parsing of scenario YAML files
type Parser struct {
	strictMode bool
}

// NewParser creates a new Parser
func NewParser() *Parser {
	return &Parser{
		strictMode: false,
	}
}

// NewStrictParser creates a parser that fails on unknown fields
func NewStrictParser() *Parser {
	return &Parser{
		strictMode: true,
	}
}

// ParseFile reads and parses a scenario from a YAML file
func (p *Parser) ParseFile(path string) (*Scenario, error) {
	absPath, err := filepath.Abs(path)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve path: %w", err)
	}

	data, err := os.ReadFile(absPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	return p.Parse(data)
}

// Parse parses a scenario from YAML bytes
func (p *Parser) Parse(data []byte) (*Scenario, error) {
	var scenario Scenario

	decoder := yaml.NewDecoder(strings.NewReader(string(data)))
	if p.strictMode {
		decoder.KnownFields(true)
	}

	if err := decoder.Decode(&scenario); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}

	// Apply defaults
	p.applyDefaults(&scenario)

	// Validate
	if err := scenario.Validate(); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}

	return &scenario, nil
}

// applyDefaults sets default values for optional fields
func (p *Parser) applyDefaults(s *Scenario) {
	if s.Version == "" {
		s.Version = "1.0"
	}

	if s.Variables == nil {
		s.Variables = make(map[string]string)
	}

	for i := range s.Steps {
		step := &s.Steps[i]

		// Default method is GET
		if step.Request.Method == "" {
			step.Request.Method = "GET"
		}

		// Normalize method to uppercase
		step.Request.Method = strings.ToUpper(step.Request.Method)

		// Default timeout
		if step.Request.Timeout == 0 {
			step.Request.Timeout = 30 * time.Second
		}

		// Initialize headers map if nil
		if step.Request.Headers == nil {
			step.Request.Headers = make(map[string]string)
		}

		// Set default Content-Type for POST/PUT/PATCH with body
		if step.Request.Body != "" {
			if step.Request.ContentType == "" && step.Request.Headers["Content-Type"] == "" {
				// Try to infer content type from body
				step.Request.ContentType = p.inferContentType(step.Request.Body)
			}
		}

		// Default retry config
		if step.Retry != nil && step.Retry.Count == 0 {
			step.Retry.Count = 3
		}
		if step.Retry != nil && step.Retry.Delay == 0 {
			step.Retry.Delay = 1 * time.Second
		}
	}
}

// inferContentType tries to determine content type from body
func (p *Parser) inferContentType(body string) string {
	trimmed := strings.TrimSpace(body)
	if strings.HasPrefix(trimmed, "{") || strings.HasPrefix(trimmed, "[") {
		return "application/json"
	}
	if strings.HasPrefix(trimmed, "<?xml") || strings.HasPrefix(trimmed, "<") {
		return "application/xml"
	}
	if strings.Contains(trimmed, "=") && !strings.Contains(trimmed, " ") {
		return "application/x-www-form-urlencoded"
	}
	return "text/plain"
}

// ParseMultiple parses multiple scenarios from a directory
func (p *Parser) ParseMultiple(dir string) ([]*Scenario, error) {
	var scenarios []*Scenario

	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("failed to read directory: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		name := entry.Name()
		if !strings.HasSuffix(name, ".yaml") && !strings.HasSuffix(name, ".yml") {
			continue
		}

		path := filepath.Join(dir, name)
		scenario, err := p.ParseFile(path)
		if err != nil {
			return nil, fmt.Errorf("failed to parse %s: %w", name, err)
		}

		scenarios = append(scenarios, scenario)
	}

	return scenarios, nil
}

// ValidateOnly parses and validates without returning the scenario
func (p *Parser) ValidateOnly(data []byte) error {
	_, err := p.Parse(data)
	return err
}

// scenarioYAML is the internal structure for YAML parsing with duration support
type scenarioYAML struct {
	Name        string            `yaml:"name"`
	Description string            `yaml:"description,omitempty"`
	Version     string            `yaml:"version,omitempty"`
	Variables   map[string]string `yaml:"variables,omitempty"`
	Steps       []stepYAML        `yaml:"steps"`
}

type stepYAML struct {
	Name      string           `yaml:"name"`
	Request   requestYAML      `yaml:"request"`
	Extract   []ExtractionRule `yaml:"extract,omitempty"`
	Assert    []Assertion      `yaml:"assert,omitempty"`
	OnSuccess string           `yaml:"on_success,omitempty"`
	OnFailure string           `yaml:"on_failure,omitempty"`
	Condition string           `yaml:"condition,omitempty"`
	Delay     string           `yaml:"delay,omitempty"`
	Retry     *retryYAML       `yaml:"retry,omitempty"`
	Tags      []string         `yaml:"tags,omitempty"`
}

type requestYAML struct {
	Method      string            `yaml:"method"`
	URL         string            `yaml:"url"`
	Headers     map[string]string `yaml:"headers,omitempty"`
	Body        string            `yaml:"body,omitempty"`
	ContentType string            `yaml:"content_type,omitempty"`
	Timeout     string            `yaml:"timeout,omitempty"`
}

type retryYAML struct {
	Count    int    `yaml:"count"`
	Delay    string `yaml:"delay,omitempty"`
	OnStatus []int  `yaml:"on_status,omitempty"`
}

// ParseWithDurationStrings parses YAML with string-based duration fields
func (p *Parser) ParseWithDurationStrings(data []byte) (*Scenario, error) {
	var raw scenarioYAML

	if err := yaml.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}

	scenario := &Scenario{
		Name:        raw.Name,
		Description: raw.Description,
		Version:     raw.Version,
		Variables:   raw.Variables,
		Steps:       make([]Step, len(raw.Steps)),
	}

	for i, rawStep := range raw.Steps {
		step := Step{
			Name:      rawStep.Name,
			Extract:   rawStep.Extract,
			Assert:    rawStep.Assert,
			OnSuccess: rawStep.OnSuccess,
			OnFailure: rawStep.OnFailure,
			Condition: rawStep.Condition,
			Tags:      rawStep.Tags,
			Request: RequestConfig{
				Method:      rawStep.Request.Method,
				URL:         rawStep.Request.URL,
				Headers:     rawStep.Request.Headers,
				Body:        rawStep.Request.Body,
				ContentType: rawStep.Request.ContentType,
			},
		}

		// Parse delay duration
		if rawStep.Delay != "" {
			d, err := time.ParseDuration(rawStep.Delay)
			if err != nil {
				return nil, fmt.Errorf("step '%s': invalid delay '%s': %w", rawStep.Name, rawStep.Delay, err)
			}
			step.Delay = d
		}

		// Parse timeout duration
		if rawStep.Request.Timeout != "" {
			t, err := time.ParseDuration(rawStep.Request.Timeout)
			if err != nil {
				return nil, fmt.Errorf("step '%s': invalid timeout '%s': %w", rawStep.Name, rawStep.Request.Timeout, err)
			}
			step.Request.Timeout = t
		}

		// Parse retry config
		if rawStep.Retry != nil {
			step.Retry = &RetryConfig{
				Count:    rawStep.Retry.Count,
				OnStatus: rawStep.Retry.OnStatus,
			}
			if rawStep.Retry.Delay != "" {
				d, err := time.ParseDuration(rawStep.Retry.Delay)
				if err != nil {
					return nil, fmt.Errorf("step '%s': invalid retry delay '%s': %w", rawStep.Name, rawStep.Retry.Delay, err)
				}
				step.Retry.Delay = d
			}
		}

		scenario.Steps[i] = step
	}

	p.applyDefaults(scenario)

	if err := scenario.Validate(); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}

	return scenario, nil
}
