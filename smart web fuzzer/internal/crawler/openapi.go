// Package crawler provides OpenAPI/Swagger specification parsing.
package crawler

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// OpenAPISpec represents an OpenAPI specification
type OpenAPISpec struct {
	OpenAPI    string              `json:"openapi" yaml:"openapi"`
	Swagger    string              `json:"swagger" yaml:"swagger"`
	Info       OpenAPIInfo         `json:"info" yaml:"info"`
	Servers    []OpenAPIServer     `json:"servers" yaml:"servers"`
	Paths      map[string]PathItem `json:"paths" yaml:"paths"`
	Components OpenAPIComponents   `json:"components" yaml:"components"`
	BasePath   string              `json:"basePath" yaml:"basePath"` // Swagger 2.0
	Host       string              `json:"host" yaml:"host"`         // Swagger 2.0
	Schemes    []string            `json:"schemes" yaml:"schemes"`   // Swagger 2.0
}

// OpenAPIInfo contains API metadata
type OpenAPIInfo struct {
	Title       string `json:"title" yaml:"title"`
	Description string `json:"description" yaml:"description"`
	Version     string `json:"version" yaml:"version"`
}

// OpenAPIServer represents a server
type OpenAPIServer struct {
	URL         string `json:"url" yaml:"url"`
	Description string `json:"description" yaml:"description"`
}

// PathItem represents operations on a path
type PathItem struct {
	Get     *Operation `json:"get" yaml:"get"`
	Post    *Operation `json:"post" yaml:"post"`
	Put     *Operation `json:"put" yaml:"put"`
	Delete  *Operation `json:"delete" yaml:"delete"`
	Patch   *Operation `json:"patch" yaml:"patch"`
	Options *Operation `json:"options" yaml:"options"`
	Head    *Operation `json:"head" yaml:"head"`
}

// Operation represents an API operation
type Operation struct {
	OperationID string                `json:"operationId" yaml:"operationId"`
	Summary     string                `json:"summary" yaml:"summary"`
	Description string                `json:"description" yaml:"description"`
	Tags        []string              `json:"tags" yaml:"tags"`
	Parameters  []OpenAPIParam        `json:"parameters" yaml:"parameters"`
	RequestBody *RequestBody          `json:"requestBody" yaml:"requestBody"`
	Responses   map[string]Response   `json:"responses" yaml:"responses"`
	Security    []map[string][]string `json:"security" yaml:"security"`
}

// OpenAPIParam represents a parameter
type OpenAPIParam struct {
	Name        string  `json:"name" yaml:"name"`
	In          string  `json:"in" yaml:"in"` // query, header, path, cookie
	Description string  `json:"description" yaml:"description"`
	Required    bool    `json:"required" yaml:"required"`
	Schema      *Schema `json:"schema" yaml:"schema"`
	Type        string  `json:"type" yaml:"type"` // Swagger 2.0
}

// RequestBody represents a request body
type RequestBody struct {
	Description string               `json:"description" yaml:"description"`
	Required    bool                 `json:"required" yaml:"required"`
	Content     map[string]MediaType `json:"content" yaml:"content"`
}

// MediaType represents a media type
type MediaType struct {
	Schema   *Schema            `json:"schema" yaml:"schema"`
	Example  interface{}        `json:"example" yaml:"example"`
	Examples map[string]Example `json:"examples" yaml:"examples"`
}

// Schema represents a JSON schema
type Schema struct {
	Type       string             `json:"type" yaml:"type"`
	Format     string             `json:"format" yaml:"format"`
	Properties map[string]*Schema `json:"properties" yaml:"properties"`
	Items      *Schema            `json:"items" yaml:"items"`
	Ref        string             `json:"$ref" yaml:"$ref"`
	Required   []string           `json:"required" yaml:"required"`
	Enum       []interface{}      `json:"enum" yaml:"enum"`
	Example    interface{}        `json:"example" yaml:"example"`
}

// Example represents an example
type Example struct {
	Summary string      `json:"summary" yaml:"summary"`
	Value   interface{} `json:"value" yaml:"value"`
}

// Response represents an API response
type Response struct {
	Description string               `json:"description" yaml:"description"`
	Content     map[string]MediaType `json:"content" yaml:"content"`
}

// OpenAPIComponents contains reusable components
type OpenAPIComponents struct {
	Schemas         map[string]*Schema        `json:"schemas" yaml:"schemas"`
	SecuritySchemes map[string]SecurityScheme `json:"securitySchemes" yaml:"securitySchemes"`
}

// SecurityScheme represents a security scheme
type SecurityScheme struct {
	Type         string `json:"type" yaml:"type"`
	Scheme       string `json:"scheme" yaml:"scheme"`
	BearerFormat string `json:"bearerFormat" yaml:"bearerFormat"`
	In           string `json:"in" yaml:"in"`
	Name         string `json:"name" yaml:"name"`
}

// APIEndpoint represents an extracted API endpoint
type APIEndpoint struct {
	URL         string
	Method      string
	Summary     string
	Description string
	Parameters  []Parameter
	ContentType string
	Security    []string
	Tags        []string
}

// OpenAPIParser parses OpenAPI/Swagger specs
type OpenAPIParser struct {
	client  *http.Client
	timeout time.Duration
}

// NewOpenAPIParser creates a new OpenAPI parser
func NewOpenAPIParser() *OpenAPIParser {
	return &OpenAPIParser{
		client:  &http.Client{Timeout: 30 * time.Second},
		timeout: 30 * time.Second,
	}
}

// Parse parses an OpenAPI spec from URL
func (p *OpenAPIParser) Parse(ctx context.Context, specURL string) (*OpenAPISpec, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", specURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "FluxFuzzer/1.0")

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	return p.ParseBytes(body)
}

// ParseBytes parses OpenAPI spec from bytes
func (p *OpenAPIParser) ParseBytes(data []byte) (*OpenAPISpec, error) {
	var spec OpenAPISpec

	// Try JSON first
	if err := json.Unmarshal(data, &spec); err != nil {
		// Try YAML
		if err := yaml.Unmarshal(data, &spec); err != nil {
			return nil, fmt.Errorf("failed to parse as JSON or YAML: %w", err)
		}
	}

	return &spec, nil
}

// DiscoverSpecs attempts to discover OpenAPI specs at common locations
func (p *OpenAPIParser) DiscoverSpecs(ctx context.Context, baseURL string) []string {
	commonPaths := []string{
		"/openapi.json",
		"/openapi.yaml",
		"/swagger.json",
		"/swagger.yaml",
		"/api-docs",
		"/api/swagger.json",
		"/api/openapi.json",
		"/v1/api-docs",
		"/v2/api-docs",
		"/v3/api-docs",
		"/docs/swagger.json",
		"/swagger/v1/swagger.json",
	}

	baseURL = strings.TrimSuffix(baseURL, "/")

	var discovered []string
	for _, path := range commonPaths {
		testURL := baseURL + path

		req, err := http.NewRequestWithContext(ctx, "HEAD", testURL, nil)
		if err != nil {
			continue
		}

		resp, err := p.client.Do(req)
		if err != nil {
			continue
		}
		resp.Body.Close()

		if resp.StatusCode == 200 {
			contentType := resp.Header.Get("Content-Type")
			if strings.Contains(contentType, "json") ||
				strings.Contains(contentType, "yaml") ||
				strings.Contains(contentType, "text") {
				discovered = append(discovered, testURL)
			}
		}
	}

	return discovered
}

// ExtractEndpoints extracts API endpoints from spec
func (p *OpenAPIParser) ExtractEndpoints(spec *OpenAPISpec, baseURL string) []APIEndpoint {
	var endpoints []APIEndpoint

	// Determine base URL
	serverURL := baseURL
	if len(spec.Servers) > 0 {
		serverURL = spec.Servers[0].URL
	} else if spec.Host != "" {
		// Swagger 2.0
		scheme := "https"
		if len(spec.Schemes) > 0 {
			scheme = spec.Schemes[0]
		}
		serverURL = fmt.Sprintf("%s://%s%s", scheme, spec.Host, spec.BasePath)
	}

	// Handle relative server URLs
	if strings.HasPrefix(serverURL, "/") {
		if parsed, err := url.Parse(baseURL); err == nil {
			serverURL = fmt.Sprintf("%s://%s%s", parsed.Scheme, parsed.Host, serverURL)
		}
	}

	serverURL = strings.TrimSuffix(serverURL, "/")

	for path, item := range spec.Paths {
		fullPath := serverURL + path

		operations := map[string]*Operation{
			"GET":     item.Get,
			"POST":    item.Post,
			"PUT":     item.Put,
			"DELETE":  item.Delete,
			"PATCH":   item.Patch,
			"OPTIONS": item.Options,
			"HEAD":    item.Head,
		}

		for method, op := range operations {
			if op == nil {
				continue
			}

			endpoint := APIEndpoint{
				URL:         fullPath,
				Method:      method,
				Summary:     op.Summary,
				Description: op.Description,
				Tags:        op.Tags,
			}

			// Extract parameters
			for _, param := range op.Parameters {
				endpoint.Parameters = append(endpoint.Parameters, Parameter{
					Name:     param.Name,
					Location: param.In,
					Type:     p.getParamType(param),
				})
			}

			// Extract request body parameters
			if op.RequestBody != nil {
				for contentType, media := range op.RequestBody.Content {
					endpoint.ContentType = contentType
					if media.Schema != nil && media.Schema.Properties != nil {
						for name := range media.Schema.Properties {
							endpoint.Parameters = append(endpoint.Parameters, Parameter{
								Name:     name,
								Location: "body",
							})
						}
					}
				}
			}

			// Extract security requirements
			for _, sec := range op.Security {
				for name := range sec {
					endpoint.Security = append(endpoint.Security, name)
				}
			}

			endpoints = append(endpoints, endpoint)
		}
	}

	return endpoints
}

// getParamType returns the parameter type
func (p *OpenAPIParser) getParamType(param OpenAPIParam) string {
	if param.Type != "" {
		return param.Type
	}
	if param.Schema != nil && param.Schema.Type != "" {
		return param.Schema.Type
	}
	return "string"
}

// ToResults converts API endpoints to crawler results
func (p *OpenAPIParser) ToResults(endpoints []APIEndpoint) []Result {
	var results []Result

	for _, ep := range endpoints {
		result := Result{
			URL:        ep.URL,
			Method:     ep.Method,
			Type:       URLTypeOpenAPI,
			Parameters: ep.Parameters,
		}
		results = append(results, result)
	}

	return results
}
