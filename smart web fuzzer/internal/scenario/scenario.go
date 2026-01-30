// Package scenario provides a YAML-based scenario engine for multi-step API fuzzing.
// It supports sequential execution, conditional branching, and value extraction between steps.
package scenario

import (
	"fmt"
	"time"
)

// Scenario represents a complete fuzzing scenario
type Scenario struct {
	Name        string            `yaml:"name" json:"name"`
	Description string            `yaml:"description,omitempty" json:"description,omitempty"`
	Version     string            `yaml:"version,omitempty" json:"version,omitempty"`
	Variables   map[string]string `yaml:"variables,omitempty" json:"variables,omitempty"`
	Steps       []Step            `yaml:"steps" json:"steps"`
}

// Step represents a single step in the scenario
type Step struct {
	Name      string           `yaml:"name" json:"name"`
	Request   RequestConfig    `yaml:"request" json:"request"`
	Extract   []ExtractionRule `yaml:"extract,omitempty" json:"extract,omitempty"`
	Assert    []Assertion      `yaml:"assert,omitempty" json:"assert,omitempty"`
	OnSuccess string           `yaml:"on_success,omitempty" json:"on_success,omitempty"`
	OnFailure string           `yaml:"on_failure,omitempty" json:"on_failure,omitempty"`
	Condition string           `yaml:"condition,omitempty" json:"condition,omitempty"`
	Delay     time.Duration    `yaml:"delay,omitempty" json:"delay,omitempty"`
	Retry     *RetryConfig     `yaml:"retry,omitempty" json:"retry,omitempty"`
	Tags      []string         `yaml:"tags,omitempty" json:"tags,omitempty"`
}

// RequestConfig defines the HTTP request configuration
type RequestConfig struct {
	Method      string            `yaml:"method" json:"method"`
	URL         string            `yaml:"url" json:"url"`
	Headers     map[string]string `yaml:"headers,omitempty" json:"headers,omitempty"`
	Body        string            `yaml:"body,omitempty" json:"body,omitempty"`
	ContentType string            `yaml:"content_type,omitempty" json:"content_type,omitempty"`
	Timeout     time.Duration     `yaml:"timeout,omitempty" json:"timeout,omitempty"`
}

// ExtractionRule defines how to extract values from responses
type ExtractionRule struct {
	Name      string `yaml:"name" json:"name"`
	Type      string `yaml:"type" json:"type"` // regex, jsonpath, header, cookie, xpath
	Pattern   string `yaml:"pattern" json:"pattern"`
	Group     int    `yaml:"group,omitempty" json:"group,omitempty"`
	Default   string `yaml:"default,omitempty" json:"default,omitempty"`
	Required  bool   `yaml:"required,omitempty" json:"required,omitempty"`
	Transform string `yaml:"transform,omitempty" json:"transform,omitempty"`
}

// Assertion defines a condition to verify
type Assertion struct {
	Type     AssertionType `yaml:"type" json:"type"`
	Target   string        `yaml:"target,omitempty" json:"target,omitempty"`
	Expected string        `yaml:"expected" json:"expected"`
	Negate   bool          `yaml:"negate,omitempty" json:"negate,omitempty"`
	Message  string        `yaml:"message,omitempty" json:"message,omitempty"`
}

// AssertionType defines the type of assertion
type AssertionType string

const (
	AssertStatus      AssertionType = "status"       // HTTP status code
	AssertContains    AssertionType = "contains"     // Body contains string
	AssertNotContains AssertionType = "not_contains" // Body doesn't contain string
	AssertRegex       AssertionType = "regex"        // Body matches regex
	AssertJSONPath    AssertionType = "jsonpath"     // JSON path value equals
	AssertHeader      AssertionType = "header"       // Header value equals
	AssertLength      AssertionType = "length"       // Body length comparison
	AssertTime        AssertionType = "time"         // Response time comparison
)

// RetryConfig defines retry behavior for a step
type RetryConfig struct {
	Count    int           `yaml:"count" json:"count"`
	Delay    time.Duration `yaml:"delay,omitempty" json:"delay,omitempty"`
	OnStatus []int         `yaml:"on_status,omitempty" json:"on_status,omitempty"`
}

// StepResult contains the result of executing a single step
type StepResult struct {
	StepName     string            `json:"step_name"`
	Success      bool              `json:"success"`
	StatusCode   int               `json:"status_code"`
	ResponseTime time.Duration     `json:"response_time"`
	BodyLength   int               `json:"body_length"`
	Extractions  map[string]string `json:"extractions,omitempty"`
	Assertions   []AssertionResult `json:"assertions,omitempty"`
	Error        string            `json:"error,omitempty"`
	Timestamp    time.Time         `json:"timestamp"`
	RetryCount   int               `json:"retry_count,omitempty"`
}

// AssertionResult contains the result of a single assertion
type AssertionResult struct {
	Type     AssertionType `json:"type"`
	Expected string        `json:"expected"`
	Actual   string        `json:"actual"`
	Passed   bool          `json:"passed"`
	Message  string        `json:"message,omitempty"`
}

// ExecutionResult contains the overall scenario execution result
type ExecutionResult struct {
	ScenarioName string            `json:"scenario_name"`
	Success      bool              `json:"success"`
	StartTime    time.Time         `json:"start_time"`
	EndTime      time.Time         `json:"end_time"`
	Duration     time.Duration     `json:"duration"`
	StepResults  []StepResult      `json:"step_results"`
	Variables    map[string]string `json:"variables,omitempty"`
	Error        string            `json:"error,omitempty"`
}

// Validate validates the scenario configuration
func (s *Scenario) Validate() error {
	if s.Name == "" {
		return fmt.Errorf("scenario name is required")
	}
	if len(s.Steps) == 0 {
		return fmt.Errorf("scenario must have at least one step")
	}

	stepNames := make(map[string]bool)
	for i, step := range s.Steps {
		if step.Name == "" {
			return fmt.Errorf("step %d: name is required", i+1)
		}
		if stepNames[step.Name] {
			return fmt.Errorf("step %d: duplicate step name '%s'", i+1, step.Name)
		}
		stepNames[step.Name] = true

		if err := step.Validate(); err != nil {
			return fmt.Errorf("step '%s': %w", step.Name, err)
		}
	}

	// Validate step references
	for _, step := range s.Steps {
		if step.OnSuccess != "" && !stepNames[step.OnSuccess] {
			return fmt.Errorf("step '%s': on_success references unknown step '%s'", step.Name, step.OnSuccess)
		}
		if step.OnFailure != "" && !stepNames[step.OnFailure] {
			return fmt.Errorf("step '%s': on_failure references unknown step '%s'", step.Name, step.OnFailure)
		}
	}

	return nil
}

// Validate validates the step configuration
func (s *Step) Validate() error {
	if err := s.Request.Validate(); err != nil {
		return fmt.Errorf("request: %w", err)
	}

	for i, extract := range s.Extract {
		if extract.Name == "" {
			return fmt.Errorf("extraction %d: name is required", i+1)
		}
		if extract.Type == "" {
			return fmt.Errorf("extraction '%s': type is required", extract.Name)
		}
		if extract.Pattern == "" {
			return fmt.Errorf("extraction '%s': pattern is required", extract.Name)
		}
	}

	for i, assert := range s.Assert {
		if assert.Type == "" {
			return fmt.Errorf("assertion %d: type is required", i+1)
		}
	}

	return nil
}

// Validate validates the request configuration
func (r *RequestConfig) Validate() error {
	if r.Method == "" {
		return fmt.Errorf("method is required")
	}
	if r.URL == "" {
		return fmt.Errorf("url is required")
	}
	return nil
}

// GetStepByName returns a step by its name
func (s *Scenario) GetStepByName(name string) (*Step, int) {
	for i := range s.Steps {
		if s.Steps[i].Name == name {
			return &s.Steps[i], i
		}
	}
	return nil, -1
}

// GetStepNames returns all step names in order
func (s *Scenario) GetStepNames() []string {
	names := make([]string, len(s.Steps))
	for i, step := range s.Steps {
		names[i] = step.Name
	}
	return names
}

// HasConditionalFlow returns true if any step has conditional branching
func (s *Scenario) HasConditionalFlow() bool {
	for _, step := range s.Steps {
		if step.OnSuccess != "" || step.OnFailure != "" || step.Condition != "" {
			return true
		}
	}
	return false
}

// Clone creates a deep copy of the scenario
func (s *Scenario) Clone() *Scenario {
	clone := &Scenario{
		Name:        s.Name,
		Description: s.Description,
		Version:     s.Version,
		Variables:   make(map[string]string),
		Steps:       make([]Step, len(s.Steps)),
	}

	for k, v := range s.Variables {
		clone.Variables[k] = v
	}

	copy(clone.Steps, s.Steps)
	return clone
}
