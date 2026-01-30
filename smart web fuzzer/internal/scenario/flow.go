// Package scenario provides execution flow control for scenarios.
package scenario

import (
	"context"
	"fmt"
	"io"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/tidwall/gjson"
)

// HTTPClient interface for making HTTP requests
type HTTPClient interface {
	Do(req *Request) (*Response, error)
}

// Request represents an HTTP request
type Request struct {
	Method  string
	URL     string
	Headers map[string]string
	Body    []byte
	Timeout time.Duration
}

// Response represents an HTTP response
type Response struct {
	StatusCode int
	Headers    map[string]string
	Body       []byte
	Duration   time.Duration
}

// TemplateSubstitutor interface for template substitution
type TemplateSubstitutor interface {
	Substitute(input string) string
	SetVariable(name, value string)
}

// ValueExtractor interface for value extraction
type ValueExtractor interface {
	ExtractRegex(body []byte, pattern string, group int) (string, bool)
	ExtractJSONPath(body []byte, path string) (string, bool)
}

// Executor handles scenario execution
type Executor struct {
	client      HTTPClient
	substitutor TemplateSubstitutor
	extractor   ValueExtractor

	maxSteps int
	timeout  time.Duration
	debug    bool
	onStep   func(result *StepResult)
}

// ExecutorOption configures the Executor
type ExecutorOption func(*Executor)

// WithMaxSteps sets the maximum number of steps to execute (loop protection)
func WithMaxSteps(n int) ExecutorOption {
	return func(e *Executor) {
		e.maxSteps = n
	}
}

// WithTimeout sets the overall execution timeout
func WithTimeout(d time.Duration) ExecutorOption {
	return func(e *Executor) {
		e.timeout = d
	}
}

// WithDebug enables debug mode
func WithDebug(debug bool) ExecutorOption {
	return func(e *Executor) {
		e.debug = debug
	}
}

// WithStepCallback sets a callback for each step completion
func WithStepCallback(fn func(*StepResult)) ExecutorOption {
	return func(e *Executor) {
		e.onStep = fn
	}
}

// NewExecutor creates a new scenario executor
func NewExecutor(client HTTPClient, substitutor TemplateSubstitutor, opts ...ExecutorOption) *Executor {
	e := &Executor{
		client:      client,
		substitutor: substitutor,
		maxSteps:    100,
		timeout:     5 * time.Minute,
	}

	for _, opt := range opts {
		opt(e)
	}

	return e
}

// SetExtractor sets the value extractor
func (e *Executor) SetExtractor(ext ValueExtractor) {
	e.extractor = ext
}

// Execute runs the scenario and returns the result
func (e *Executor) Execute(scenario *Scenario) (*ExecutionResult, error) {
	return e.ExecuteWithContext(context.Background(), scenario)
}

// ExecuteWithContext runs the scenario with context
func (e *Executor) ExecuteWithContext(ctx context.Context, scenario *Scenario) (*ExecutionResult, error) {
	if err := scenario.Validate(); err != nil {
		return nil, fmt.Errorf("invalid scenario: %w", err)
	}

	// Apply scenario variables to substitutor
	if e.substitutor != nil {
		for name, value := range scenario.Variables {
			e.substitutor.SetVariable(name, value)
		}
	}

	result := &ExecutionResult{
		ScenarioName: scenario.Name,
		StartTime:    time.Now(),
		StepResults:  make([]StepResult, 0, len(scenario.Steps)),
		Variables:    make(map[string]string),
	}

	// Copy initial variables
	for k, v := range scenario.Variables {
		result.Variables[k] = v
	}

	// Create timeout context
	execCtx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()

	// Execute steps
	stepCount := 0
	currentStepIdx := 0

	for currentStepIdx < len(scenario.Steps) && stepCount < e.maxSteps {
		select {
		case <-execCtx.Done():
			result.Success = false
			result.Error = "execution timeout"
			result.EndTime = time.Now()
			result.Duration = result.EndTime.Sub(result.StartTime)
			return result, nil
		default:
		}

		step := &scenario.Steps[currentStepIdx]
		stepCount++

		// Check condition
		if step.Condition != "" {
			if !e.evaluateCondition(step.Condition) {
				// Skip this step
				currentStepIdx++
				continue
			}
		}

		// Apply delay if specified
		if step.Delay > 0 {
			select {
			case <-execCtx.Done():
				result.Success = false
				result.Error = "execution timeout during delay"
				break
			case <-time.After(step.Delay):
			}
		}

		// Execute step with retry
		stepResult := e.executeStepWithRetry(execCtx, step)
		result.StepResults = append(result.StepResults, *stepResult)

		// Call step callback if set
		if e.onStep != nil {
			e.onStep(stepResult)
		}

		// Extract values
		for name, value := range stepResult.Extractions {
			result.Variables[name] = value
		}

		// Determine next step
		if stepResult.Success {
			if step.OnSuccess != "" {
				_, nextIdx := scenario.GetStepByName(step.OnSuccess)
				if nextIdx >= 0 {
					currentStepIdx = nextIdx
					continue
				}
			}
		} else {
			if step.OnFailure != "" {
				_, nextIdx := scenario.GetStepByName(step.OnFailure)
				if nextIdx >= 0 {
					currentStepIdx = nextIdx
					continue
				}
			}
			// If no on_failure handler and step failed, stop execution
			result.Success = false
			result.Error = fmt.Sprintf("step '%s' failed: %s", step.Name, stepResult.Error)
			break
		}

		currentStepIdx++
	}

	if stepCount >= e.maxSteps {
		result.Error = "max steps exceeded (possible infinite loop)"
		result.Success = false
	} else if result.Error == "" {
		result.Success = true
	}

	result.EndTime = time.Now()
	result.Duration = result.EndTime.Sub(result.StartTime)

	return result, nil
}

// executeStepWithRetry executes a step with retry logic
func (e *Executor) executeStepWithRetry(ctx context.Context, step *Step) *StepResult {
	maxRetries := 0
	retryDelay := time.Second
	retryStatuses := map[int]bool{}

	if step.Retry != nil {
		maxRetries = step.Retry.Count
		if step.Retry.Delay > 0 {
			retryDelay = step.Retry.Delay
		}
		for _, status := range step.Retry.OnStatus {
			retryStatuses[status] = true
		}
	}

	var lastResult *StepResult

	for attempt := 0; attempt <= maxRetries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				lastResult.Error = "retry cancelled: context done"
				return lastResult
			case <-time.After(retryDelay):
			}
		}

		lastResult = e.executeStep(ctx, step)
		lastResult.RetryCount = attempt

		// Check if we should retry
		if lastResult.Success {
			return lastResult
		}

		// Check if status is retryable
		if len(retryStatuses) > 0 && !retryStatuses[lastResult.StatusCode] {
			return lastResult
		}
	}

	return lastResult
}

// executeStep executes a single step
func (e *Executor) executeStep(ctx context.Context, step *Step) *StepResult {
	result := &StepResult{
		StepName:    step.Name,
		Timestamp:   time.Now(),
		Extractions: make(map[string]string),
		Assertions:  make([]AssertionResult, 0, len(step.Assert)),
	}

	// Build request
	req := &Request{
		Method:  step.Request.Method,
		URL:     step.Request.URL,
		Headers: make(map[string]string),
		Timeout: step.Request.Timeout,
	}

	// Apply template substitution
	if e.substitutor != nil {
		req.URL = e.substitutor.Substitute(req.URL)
		if step.Request.Body != "" {
			req.Body = []byte(e.substitutor.Substitute(step.Request.Body))
		}
	} else {
		if step.Request.Body != "" {
			req.Body = []byte(step.Request.Body)
		}
	}

	// Copy and substitute headers
	for k, v := range step.Request.Headers {
		if e.substitutor != nil {
			req.Headers[k] = e.substitutor.Substitute(v)
		} else {
			req.Headers[k] = v
		}
	}

	// Set Content-Type if specified
	if step.Request.ContentType != "" {
		req.Headers["Content-Type"] = step.Request.ContentType
	}

	// Execute request
	if e.client == nil {
		result.Error = "HTTP client not configured"
		return result
	}

	resp, err := e.client.Do(req)
	if err != nil {
		result.Error = fmt.Sprintf("request failed: %v", err)
		return result
	}

	result.StatusCode = resp.StatusCode
	result.ResponseTime = resp.Duration
	result.BodyLength = len(resp.Body)

	// Extract values
	for _, extract := range step.Extract {
		value, found := e.extractValue(resp, &extract)
		if found {
			result.Extractions[extract.Name] = value
			if e.substitutor != nil {
				e.substitutor.SetVariable(extract.Name, value)
			}
		} else if extract.Default != "" {
			result.Extractions[extract.Name] = extract.Default
			if e.substitutor != nil {
				e.substitutor.SetVariable(extract.Name, extract.Default)
			}
		} else if extract.Required {
			result.Error = fmt.Sprintf("required extraction '%s' not found", extract.Name)
			return result
		}
	}

	// Run assertions
	allPassed := true
	for _, assert := range step.Assert {
		assertResult := e.runAssertion(resp, &assert)
		result.Assertions = append(result.Assertions, assertResult)
		if !assertResult.Passed {
			allPassed = false
		}
	}

	result.Success = allPassed && result.Error == ""
	return result
}

// extractValue extracts a value from the response
func (e *Executor) extractValue(resp *Response, extract *ExtractionRule) (string, bool) {
	switch strings.ToLower(extract.Type) {
	case "regex":
		return e.extractRegex(resp.Body, extract.Pattern, extract.Group)
	case "jsonpath":
		return e.extractJSONPath(resp.Body, extract.Pattern)
	case "header":
		if v, ok := resp.Headers[extract.Pattern]; ok {
			return v, true
		}
		// Case-insensitive header lookup
		for k, v := range resp.Headers {
			if strings.EqualFold(k, extract.Pattern) {
				return v, true
			}
		}
		return "", false
	case "cookie":
		return e.extractCookie(resp.Headers, extract.Pattern)
	default:
		return "", false
	}
}

// extractRegex extracts a value using regex
func (e *Executor) extractRegex(body []byte, pattern string, group int) (string, bool) {
	if e.extractor != nil {
		return e.extractor.ExtractRegex(body, pattern, group)
	}

	re, err := regexp.Compile(pattern)
	if err != nil {
		return "", false
	}

	matches := re.FindSubmatch(body)
	if len(matches) == 0 {
		return "", false
	}

	if group < len(matches) {
		return string(matches[group]), true
	}
	return string(matches[0]), true
}

// extractJSONPath extracts a value using JSON path
func (e *Executor) extractJSONPath(body []byte, path string) (string, bool) {
	if e.extractor != nil {
		return e.extractor.ExtractJSONPath(body, path)
	}

	result := gjson.GetBytes(body, path)
	if !result.Exists() {
		return "", false
	}
	return result.String(), true
}

// extractCookie extracts a cookie value from Set-Cookie header
func (e *Executor) extractCookie(headers map[string]string, name string) (string, bool) {
	setCookie := headers["Set-Cookie"]
	if setCookie == "" {
		setCookie = headers["set-cookie"]
	}
	if setCookie == "" {
		return "", false
	}

	// Parse Set-Cookie header
	parts := strings.Split(setCookie, ";")
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if idx := strings.Index(part, "="); idx > 0 {
			cookieName := part[:idx]
			if cookieName == name {
				return part[idx+1:], true
			}
		}
	}
	return "", false
}

// runAssertion runs a single assertion
func (e *Executor) runAssertion(resp *Response, assert *Assertion) AssertionResult {
	result := AssertionResult{
		Type:     assert.Type,
		Expected: assert.Expected,
		Message:  assert.Message,
	}

	var passed bool

	switch assert.Type {
	case AssertStatus:
		result.Actual = strconv.Itoa(resp.StatusCode)
		expected, err := strconv.Atoi(assert.Expected)
		if err == nil {
			passed = resp.StatusCode == expected
		}

	case AssertContains:
		result.Actual = fmt.Sprintf("body length: %d", len(resp.Body))
		passed = strings.Contains(string(resp.Body), assert.Expected)

	case AssertNotContains:
		result.Actual = fmt.Sprintf("body length: %d", len(resp.Body))
		passed = !strings.Contains(string(resp.Body), assert.Expected)

	case AssertRegex:
		re, err := regexp.Compile(assert.Expected)
		if err != nil {
			result.Message = fmt.Sprintf("invalid regex: %v", err)
			passed = false
		} else {
			passed = re.Match(resp.Body)
			result.Actual = fmt.Sprintf("matches: %v", passed)
		}

	case AssertJSONPath:
		value := gjson.GetBytes(resp.Body, assert.Target)
		result.Actual = value.String()
		passed = value.String() == assert.Expected

	case AssertHeader:
		value := resp.Headers[assert.Target]
		if value == "" {
			// Case-insensitive lookup
			for k, v := range resp.Headers {
				if strings.EqualFold(k, assert.Target) {
					value = v
					break
				}
			}
		}
		result.Actual = value
		passed = value == assert.Expected

	case AssertLength:
		result.Actual = strconv.Itoa(len(resp.Body))
		expected, err := strconv.Atoi(assert.Expected)
		if err == nil {
			// Support comparison operators
			if strings.HasPrefix(assert.Expected, ">") {
				expected, _ = strconv.Atoi(strings.TrimPrefix(assert.Expected, ">"))
				passed = len(resp.Body) > expected
			} else if strings.HasPrefix(assert.Expected, "<") {
				expected, _ = strconv.Atoi(strings.TrimPrefix(assert.Expected, "<"))
				passed = len(resp.Body) < expected
			} else {
				passed = len(resp.Body) == expected
			}
		}

	case AssertTime:
		result.Actual = resp.Duration.String()
		expected, err := time.ParseDuration(assert.Expected)
		if err == nil {
			passed = resp.Duration <= expected
		}

	default:
		result.Message = fmt.Sprintf("unknown assertion type: %s", assert.Type)
		passed = false
	}

	// Apply negation
	if assert.Negate {
		passed = !passed
	}

	result.Passed = passed
	if !passed && result.Message == "" {
		result.Message = fmt.Sprintf("expected %s to be %s, got %s", assert.Type, assert.Expected, result.Actual)
	}

	return result
}

// evaluateCondition evaluates a condition string
func (e *Executor) evaluateCondition(condition string) bool {
	if e.substitutor == nil {
		return true
	}

	// Simple condition evaluation
	// Supports: exists:var, !exists:var, var==value, var!=value

	condition = strings.TrimSpace(condition)

	// Negation
	negate := false
	if strings.HasPrefix(condition, "!") {
		negate = true
		condition = strings.TrimPrefix(condition, "!")
	}

	var result bool

	if strings.HasPrefix(condition, "exists:") {
		varName := strings.TrimPrefix(condition, "exists:")
		substituted := e.substitutor.Substitute("{{" + varName + "}}")
		result = substituted != "{{"+varName+"}}"
	} else if strings.Contains(condition, "==") {
		parts := strings.SplitN(condition, "==", 2)
		if len(parts) == 2 {
			left := e.substitutor.Substitute("{{" + strings.TrimSpace(parts[0]) + "}}")
			right := strings.TrimSpace(parts[1])
			result = left == right
		}
	} else if strings.Contains(condition, "!=") {
		parts := strings.SplitN(condition, "!=", 2)
		if len(parts) == 2 {
			left := e.substitutor.Substitute("{{" + strings.TrimSpace(parts[0]) + "}}")
			right := strings.TrimSpace(parts[1])
			result = left != right
		}
	} else {
		// Treat as variable existence check
		substituted := e.substitutor.Substitute("{{" + condition + "}}")
		result = substituted != "{{"+condition+"}}"
	}

	if negate {
		return !result
	}
	return result
}

// Ensure io is used (for future streaming support)
var _ io.Reader
