package crawler

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestNewCrawler(t *testing.T) {
	c := New(nil)
	if c == nil {
		t.Fatal("New returned nil")
	}

	if c.config.MaxDepth != 3 {
		t.Errorf("Expected default MaxDepth 3, got %d", c.config.MaxDepth)
	}

	if c.config.Concurrency != 5 {
		t.Errorf("Expected default Concurrency 5, got %d", c.config.Concurrency)
	}
}

func TestCrawler_WithConfig(t *testing.T) {
	config := &Config{
		MaxDepth:    5,
		MaxURLs:     500,
		Timeout:     5 * time.Second,
		Concurrency: 3,
		RateLimit:   20,
	}

	c := New(config)

	if c.config.MaxDepth != 5 {
		t.Errorf("Expected MaxDepth 5, got %d", c.config.MaxDepth)
	}

	if c.config.MaxURLs != 500 {
		t.Errorf("Expected MaxURLs 500, got %d", c.config.MaxURLs)
	}
}

func TestCrawler_ResolveURL(t *testing.T) {
	c := New(nil)

	tests := []struct {
		base     string
		href     string
		expected string
	}{
		{"http://example.com/page", "/other", "http://example.com/other"},
		{"http://example.com/dir/", "file.html", "http://example.com/dir/file.html"},
		{"http://example.com", "http://other.com/page", "http://other.com/page"},
		{"http://example.com", "#anchor", ""},
		{"http://example.com", "javascript:void(0)", ""},
		{"http://example.com", "mailto:test@test.com", ""},
	}

	for _, tt := range tests {
		base, _ := parseURL(tt.base)
		result := c.resolveURL(base, tt.href)
		if result != tt.expected {
			t.Errorf("resolveURL(%s, %s) = %s, want %s", tt.base, tt.href, result, tt.expected)
		}
	}
}

func TestCrawler_IsAllowed(t *testing.T) {
	config := &Config{
		AllowedDomains:  []string{"example.com"},
		ExcludePatterns: []string{`\.pdf$`, `/admin/`},
	}
	c := New(config)

	tests := []struct {
		url      string
		expected bool
	}{
		{"http://example.com/page", true},
		{"http://sub.example.com/page", true},
		{"http://other.com/page", false},
		{"http://example.com/file.pdf", false},
		{"http://example.com/admin/dashboard", false},
	}

	for _, tt := range tests {
		result := c.isAllowed(tt.url)
		if result != tt.expected {
			t.Errorf("isAllowed(%s) = %v, want %v", tt.url, result, tt.expected)
		}
	}
}

func TestCrawler_DetermineURLType(t *testing.T) {
	c := New(nil)

	tests := []struct {
		url         string
		contentType string
		expected    URLType
	}{
		{"http://example.com/api/users", "application/json", URLTypeAPI},
		{"http://example.com/script.js", "application/javascript", URLTypeJS},
		{"http://example.com/page", "text/html", URLTypePage},
		{"http://example.com/v1/data", "text/html", URLTypeAPI},
		{"http://example.com/style.css", "text/css", URLTypeStatic},
	}

	for _, tt := range tests {
		resp := &http.Response{
			Header: http.Header{"Content-Type": []string{tt.contentType}},
		}
		result := c.determineURLType(tt.url, resp)
		if result != tt.expected {
			t.Errorf("determineURLType(%s) = %s, want %s", tt.url, result, tt.expected)
		}
	}
}

func TestCrawler_Crawl(t *testing.T) {
	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/":
			w.Header().Set("Content-Type", "text/html")
			w.Write([]byte(`
				<html>
				<body>
					<a href="/page1">Page 1</a>
					<a href="/page2">Page 2</a>
					<form action="/submit" method="POST">
						<input name="username" type="text">
						<input name="password" type="password">
					</form>
				</body>
				</html>
			`))
		case "/page1":
			w.Header().Set("Content-Type", "text/html")
			w.Write([]byte(`<html><body><a href="/page3">Page 3</a></body></html>`))
		case "/page2":
			w.Header().Set("Content-Type", "text/html")
			w.Write([]byte(`<html><body>Page 2 Content</body></html>`))
		case "/page3":
			w.Header().Set("Content-Type", "text/html")
			w.Write([]byte(`<html><body>Page 3 Content</body></html>`))
		case "/submit":
			w.WriteHeader(http.StatusMethodNotAllowed)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer server.Close()

	config := &Config{
		MaxDepth:    2,
		MaxURLs:     10,
		Timeout:     5 * time.Second,
		RateLimit:   100,
		Concurrency: 2,
	}

	c := New(config)
	results, err := c.Crawl(server.URL)
	if err != nil {
		t.Fatalf("Crawl failed: %v", err)
	}

	if len(results) == 0 {
		t.Error("Expected at least one result")
	}

	// Check if start URL was crawled
	foundRoot := false
	for _, r := range results {
		if r.URL == server.URL || r.URL == server.URL+"/" {
			foundRoot = true
			break
		}
	}
	if !foundRoot {
		t.Error("Start URL should be in results")
	}

	t.Logf("Crawled %d URLs", len(results))
	for _, r := range results {
		t.Logf("  %s %s (depth: %d, type: %s)", r.Method, r.URL, r.Depth, r.Type)
	}
}

func TestCrawler_FormExtraction(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`
			<html>
			<body>
				<form action="/login" method="POST" enctype="application/x-www-form-urlencoded">
					<input name="username" type="text" required>
					<input name="password" type="password" required>
					<input name="remember" type="checkbox">
					<button type="submit">Login</button>
				</form>
			</body>
			</html>
		`))
	}))
	defer server.Close()

	config := &Config{
		MaxDepth:    1,
		MaxURLs:     10,
		Timeout:     5 * time.Second,
		RateLimit:   100,
		Concurrency: 1,
	}

	c := New(config)
	_, err := c.Crawl(server.URL)
	if err != nil {
		t.Fatalf("Crawl failed: %v", err)
	}

	forms := c.GetForms()
	if len(forms) == 0 {
		t.Error("Expected at least one form")
	} else {
		form := forms[0]
		if form.Method != "POST" {
			t.Errorf("Expected POST method, got %s", form.Method)
		}
		if len(form.Inputs) < 3 {
			t.Errorf("Expected at least 3 inputs, got %d", len(form.Inputs))
		}
	}

	t.Logf("Found %d forms", len(forms))
}

// --- Sitemap Tests ---

func TestSitemapParser_ParseBytes(t *testing.T) {
	parser := NewSitemapParser()

	xml := `<?xml version="1.0" encoding="UTF-8"?>
	<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
		<url>
			<loc>http://example.com/page1</loc>
			<lastmod>2026-01-01</lastmod>
		</url>
		<url>
			<loc>http://example.com/page2</loc>
		</url>
	</urlset>`

	urls, err := parser.ParseBytes(context.Background(), []byte(xml), "http://example.com")
	if err != nil {
		t.Fatalf("ParseBytes failed: %v", err)
	}

	if len(urls) != 2 {
		t.Errorf("Expected 2 URLs, got %d", len(urls))
	}
}

// --- OpenAPI Tests ---

func TestOpenAPIParser_ParseBytes(t *testing.T) {
	parser := NewOpenAPIParser()

	json := `{
		"openapi": "3.0.0",
		"info": {"title": "Test API", "version": "1.0"},
		"servers": [{"url": "http://api.example.com"}],
		"paths": {
			"/users": {
				"get": {
					"summary": "List users",
					"parameters": [
						{"name": "page", "in": "query", "schema": {"type": "integer"}}
					]
				},
				"post": {
					"summary": "Create user",
					"requestBody": {
						"content": {
							"application/json": {
								"schema": {
									"type": "object",
									"properties": {
										"name": {"type": "string"},
										"email": {"type": "string"}
									}
								}
							}
						}
					}
				}
			}
		}
	}`

	spec, err := parser.ParseBytes([]byte(json))
	if err != nil {
		t.Fatalf("ParseBytes failed: %v", err)
	}

	if spec.OpenAPI != "3.0.0" {
		t.Errorf("Expected OpenAPI 3.0.0, got %s", spec.OpenAPI)
	}

	endpoints := parser.ExtractEndpoints(spec, "http://example.com")
	if len(endpoints) != 2 {
		t.Errorf("Expected 2 endpoints, got %d", len(endpoints))
	}

	// Check GET /users
	var getUsersEndpoint *APIEndpoint
	for i, ep := range endpoints {
		if ep.Method == "GET" && strings.HasSuffix(ep.URL, "/users") {
			getUsersEndpoint = &endpoints[i]
			break
		}
	}

	if getUsersEndpoint == nil {
		t.Error("GET /users endpoint not found")
	} else {
		if len(getUsersEndpoint.Parameters) != 1 {
			t.Errorf("Expected 1 parameter, got %d", len(getUsersEndpoint.Parameters))
		}
	}
}

func TestOpenAPIParser_Swagger2(t *testing.T) {
	parser := NewOpenAPIParser()

	json := `{
		"swagger": "2.0",
		"info": {"title": "Test API", "version": "1.0"},
		"host": "api.example.com",
		"basePath": "/v1",
		"schemes": ["https"],
		"paths": {
			"/users": {
				"get": {"summary": "List users"}
			}
		}
	}`

	spec, err := parser.ParseBytes([]byte(json))
	if err != nil {
		t.Fatalf("ParseBytes failed: %v", err)
	}

	if spec.Swagger != "2.0" {
		t.Errorf("Expected Swagger 2.0, got %s", spec.Swagger)
	}

	endpoints := parser.ExtractEndpoints(spec, "http://example.com")
	if len(endpoints) != 1 {
		t.Errorf("Expected 1 endpoint, got %d", len(endpoints))
	}

	if endpoints[0].URL != "https://api.example.com/v1/users" {
		t.Errorf("Unexpected URL: %s", endpoints[0].URL)
	}
}

// Helper
func parseURL(s string) (*url.URL, error) {
	return url.Parse(s)
}
