// Package crawler provides web crawling capabilities for FluxFuzzer.
// It discovers URLs, parses HTML/JavaScript, and extracts API endpoints.
package crawler

import (
	"context"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"sync"
	"time"

	"golang.org/x/net/html"
)

// Config holds crawler configuration
type Config struct {
	MaxDepth        int           // Maximum crawl depth
	MaxURLs         int           // Maximum URLs to discover
	Timeout         time.Duration // Request timeout
	RateLimit       int           // Requests per second
	AllowedDomains  []string      // Allowed domains to crawl
	ExcludePatterns []string      // URL patterns to exclude
	UserAgent       string        // Custom user agent
	FollowRedirects bool          // Follow HTTP redirects
	ParseJavaScript bool          // Extract URLs from JavaScript
	Concurrency     int           // Number of concurrent workers
}

// DefaultConfig returns a default configuration
func DefaultConfig() *Config {
	return &Config{
		MaxDepth:        3,
		MaxURLs:         1000,
		Timeout:         10 * time.Second,
		RateLimit:       10,
		UserAgent:       "FluxFuzzer/1.0 (Web Security Scanner)",
		FollowRedirects: true,
		ParseJavaScript: true,
		Concurrency:     5,
	}
}

// Result represents a crawled URL
type Result struct {
	URL        string            // Discovered URL
	Method     string            // HTTP method (GET, POST, etc.)
	Depth      int               // Crawl depth
	StatusCode int               // HTTP status code
	ParentURL  string            // Parent URL that linked to this
	Type       URLType           // Type of URL
	Parameters []Parameter       // Discovered parameters
	Headers    map[string]string // Response headers
	Forms      []Form            // Forms found on page
}

// URLType represents the type of discovered URL
type URLType string

const (
	URLTypePage      URLType = "page"      // HTML page
	URLTypeAPI       URLType = "api"       // API endpoint
	URLTypeStatic    URLType = "static"    // Static file
	URLTypeForm      URLType = "form"      // Form action
	URLTypeJS        URLType = "js"        // JavaScript file
	URLTypeSitemap   URLType = "sitemap"   // From sitemap
	URLTypeOpenAPI   URLType = "openapi"   // From OpenAPI spec
	URLTypeWebSocket URLType = "websocket" // WebSocket endpoint
)

// Parameter represents a URL parameter
type Parameter struct {
	Name     string // Parameter name
	Value    string // Example value
	Location string // query, body, header, path
	Type     string // Inferred type
}

// Form represents an HTML form
type Form struct {
	Action  string      // Form action URL
	Method  string      // Form method
	Inputs  []FormInput // Form inputs
	Enctype string      // Encoding type
}

// FormInput represents a form input field
type FormInput struct {
	Name     string // Input name
	Type     string // Input type
	Value    string // Default value
	Required bool   // Is required
}

// Crawler handles web crawling
type Crawler struct {
	config      *Config
	client      *http.Client
	visited     map[string]bool
	results     []Result
	queue       chan crawlTask
	wg          sync.WaitGroup
	mu          sync.RWMutex
	ctx         context.Context
	cancel      context.CancelFunc
	rateLimiter *time.Ticker
	excludeRe   []*regexp.Regexp
}

// crawlTask represents a crawl task
type crawlTask struct {
	url       string
	depth     int
	parentURL string
}

// New creates a new Crawler
func New(config *Config) *Crawler {
	if config == nil {
		config = DefaultConfig()
	}

	ctx, cancel := context.WithCancel(context.Background())

	// Ensure RateLimit is at least 1 to avoid divide by zero
	rateLimit := config.RateLimit
	if rateLimit <= 0 {
		rateLimit = 10 // default
	}

	c := &Crawler{
		config:      config,
		visited:     make(map[string]bool),
		results:     make([]Result, 0),
		queue:       make(chan crawlTask, config.MaxURLs),
		ctx:         ctx,
		cancel:      cancel,
		rateLimiter: time.NewTicker(time.Second / time.Duration(rateLimit)),
	}

	// Compile exclude patterns
	for _, pattern := range config.ExcludePatterns {
		if re, err := regexp.Compile(pattern); err == nil {
			c.excludeRe = append(c.excludeRe, re)
		}
	}

	// Setup HTTP client
	c.client = &http.Client{
		Timeout: config.Timeout,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if !config.FollowRedirects {
				return http.ErrUseLastResponse
			}
			if len(via) >= 10 {
				return http.ErrUseLastResponse
			}
			return nil
		},
	}

	return c
}

// Crawl starts crawling from the given URL
func (c *Crawler) Crawl(startURL string) ([]Result, error) {
	// Validate start URL
	parsed, err := url.Parse(startURL)
	if err != nil {
		return nil, err
	}

	// Add starting domain to allowed domains if not set
	if len(c.config.AllowedDomains) == 0 {
		c.config.AllowedDomains = []string{parsed.Host}
	}

	// Start workers
	for i := 0; i < c.config.Concurrency; i++ {
		c.wg.Add(1)
		go c.worker()
	}

	// Add start URL to queue
	c.queue <- crawlTask{url: startURL, depth: 0}

	// Wait for completion or context cancellation
	go func() {
		// Simple completion check
		time.Sleep(100 * time.Millisecond)
		for {
			c.mu.RLock()
			visitedCount := len(c.visited)
			c.mu.RUnlock()

			if visitedCount >= c.config.MaxURLs {
				c.cancel()
				return
			}

			select {
			case <-c.ctx.Done():
				return
			case <-time.After(500 * time.Millisecond):
				// Check if queue is empty and no more work
				if len(c.queue) == 0 {
					time.Sleep(1 * time.Second)
					if len(c.queue) == 0 {
						c.cancel()
						return
					}
				}
			}
		}
	}()

	c.wg.Wait()
	close(c.queue)
	c.rateLimiter.Stop()

	return c.results, nil
}

// Stop stops the crawler
func (c *Crawler) Stop() {
	c.cancel()
}

// worker processes crawl tasks
func (c *Crawler) worker() {
	defer c.wg.Done()

	for {
		select {
		case <-c.ctx.Done():
			return
		case task, ok := <-c.queue:
			if !ok {
				return
			}
			<-c.rateLimiter.C
			c.crawlURL(task)
		}
	}
}

// crawlURL crawls a single URL
func (c *Crawler) crawlURL(task crawlTask) {
	// Check if already visited
	c.mu.Lock()
	if c.visited[task.url] {
		c.mu.Unlock()
		return
	}
	c.visited[task.url] = true
	c.mu.Unlock()

	// Check depth limit
	if task.depth > c.config.MaxDepth {
		return
	}

	// Check URL limit
	c.mu.RLock()
	if len(c.results) >= c.config.MaxURLs {
		c.mu.RUnlock()
		return
	}
	c.mu.RUnlock()

	// Check if URL is allowed
	if !c.isAllowed(task.url) {
		return
	}

	// Create request
	req, err := http.NewRequestWithContext(c.ctx, "GET", task.url, nil)
	if err != nil {
		return
	}
	req.Header.Set("User-Agent", c.config.UserAgent)

	// Send request
	resp, err := c.client.Do(req)
	if err != nil {
		return
	}
	defer resp.Body.Close()

	// Create result
	result := Result{
		URL:        task.url,
		Method:     "GET",
		Depth:      task.depth,
		StatusCode: resp.StatusCode,
		ParentURL:  task.parentURL,
		Type:       c.determineURLType(task.url, resp),
		Headers:    make(map[string]string),
	}

	// Copy relevant headers
	for key, values := range resp.Header {
		if len(values) > 0 {
			result.Headers[key] = values[0]
		}
	}

	// Parse HTML if content type is HTML
	contentType := resp.Header.Get("Content-Type")
	if strings.Contains(contentType, "text/html") {
		c.parseHTML(task.url, task.depth, resp, &result)
	}

	// Store result
	c.mu.Lock()
	c.results = append(c.results, result)
	c.mu.Unlock()
}

// parseHTML parses HTML and extracts links
func (c *Crawler) parseHTML(baseURL string, depth int, resp *http.Response, result *Result) {
	doc, err := html.Parse(resp.Body)
	if err != nil {
		return
	}

	base, _ := url.Parse(baseURL)
	var links []string
	var forms []Form

	var traverse func(*html.Node)
	traverse = func(n *html.Node) {
		if n.Type == html.ElementNode {
			switch n.Data {
			case "a":
				// Extract <a href>
				for _, attr := range n.Attr {
					if attr.Key == "href" {
						if link := c.resolveURL(base, attr.Val); link != "" {
							links = append(links, link)
						}
					}
				}
			case "form":
				// Extract <form>
				form := c.parseForm(n, base)
				forms = append(forms, form)
				if form.Action != "" {
					links = append(links, form.Action)
				}
			case "script":
				// Extract <script src>
				for _, attr := range n.Attr {
					if attr.Key == "src" {
						if link := c.resolveURL(base, attr.Val); link != "" {
							links = append(links, link)
						}
					}
				}
			case "link":
				// Extract <link href>
				for _, attr := range n.Attr {
					if attr.Key == "href" {
						if link := c.resolveURL(base, attr.Val); link != "" {
							links = append(links, link)
						}
					}
				}
			case "img", "iframe", "embed", "video", "audio", "source":
				// Extract media sources
				for _, attr := range n.Attr {
					if attr.Key == "src" {
						if link := c.resolveURL(base, attr.Val); link != "" {
							links = append(links, link)
						}
					}
				}
			}
		}
		for child := n.FirstChild; child != nil; child = child.NextSibling {
			traverse(child)
		}
	}
	traverse(doc)

	result.Forms = forms

	// Queue discovered links
	for _, link := range links {
		select {
		case c.queue <- crawlTask{url: link, depth: depth + 1, parentURL: baseURL}:
		default:
			// Queue full
		}
	}
}

// parseForm parses an HTML form
func (c *Crawler) parseForm(n *html.Node, base *url.URL) Form {
	form := Form{
		Method:  "GET",
		Inputs:  make([]FormInput, 0),
		Enctype: "application/x-www-form-urlencoded",
	}

	for _, attr := range n.Attr {
		switch attr.Key {
		case "action":
			form.Action = c.resolveURL(base, attr.Val)
		case "method":
			form.Method = strings.ToUpper(attr.Val)
		case "enctype":
			form.Enctype = attr.Val
		}
	}

	if form.Action == "" {
		form.Action = base.String()
	}

	// Find inputs
	var findInputs func(*html.Node)
	findInputs = func(n *html.Node) {
		if n.Type == html.ElementNode {
			if n.Data == "input" || n.Data == "textarea" || n.Data == "select" {
				input := FormInput{}
				for _, attr := range n.Attr {
					switch attr.Key {
					case "name":
						input.Name = attr.Val
					case "type":
						input.Type = attr.Val
					case "value":
						input.Value = attr.Val
					case "required":
						input.Required = true
					}
				}
				if input.Name != "" {
					form.Inputs = append(form.Inputs, input)
				}
			}
		}
		for child := n.FirstChild; child != nil; child = child.NextSibling {
			findInputs(child)
		}
	}
	findInputs(n)

	return form
}

// resolveURL resolves a relative URL against a base URL
func (c *Crawler) resolveURL(base *url.URL, href string) string {
	// Skip invalid URLs
	if href == "" || strings.HasPrefix(href, "#") || strings.HasPrefix(href, "javascript:") ||
		strings.HasPrefix(href, "mailto:") || strings.HasPrefix(href, "tel:") ||
		strings.HasPrefix(href, "data:") {
		return ""
	}

	parsed, err := url.Parse(href)
	if err != nil {
		return ""
	}

	resolved := base.ResolveReference(parsed)
	return resolved.String()
}

// isAllowed checks if a URL is allowed to be crawled
func (c *Crawler) isAllowed(urlStr string) bool {
	parsed, err := url.Parse(urlStr)
	if err != nil {
		return false
	}

	// Check allowed domains
	allowed := false
	for _, domain := range c.config.AllowedDomains {
		if parsed.Host == domain || strings.HasSuffix(parsed.Host, "."+domain) {
			allowed = true
			break
		}
	}

	if !allowed {
		return false
	}

	// Check exclude patterns
	for _, re := range c.excludeRe {
		if re.MatchString(urlStr) {
			return false
		}
	}

	return true
}

// determineURLType determines the type of URL
func (c *Crawler) determineURLType(urlStr string, resp *http.Response) URLType {
	contentType := resp.Header.Get("Content-Type")

	// Check content type
	if strings.Contains(contentType, "application/json") {
		return URLTypeAPI
	}
	if strings.Contains(contentType, "javascript") {
		return URLTypeJS
	}

	// Check URL patterns
	lowerURL := strings.ToLower(urlStr)
	if strings.Contains(lowerURL, "/api/") || strings.Contains(lowerURL, "/v1/") ||
		strings.Contains(lowerURL, "/v2/") || strings.Contains(lowerURL, "/graphql") {
		return URLTypeAPI
	}

	// Check file extensions
	if strings.HasSuffix(lowerURL, ".js") {
		return URLTypeJS
	}
	if strings.HasSuffix(lowerURL, ".css") || strings.HasSuffix(lowerURL, ".png") ||
		strings.HasSuffix(lowerURL, ".jpg") || strings.HasSuffix(lowerURL, ".gif") ||
		strings.HasSuffix(lowerURL, ".svg") || strings.HasSuffix(lowerURL, ".ico") ||
		strings.HasSuffix(lowerURL, ".woff") || strings.HasSuffix(lowerURL, ".woff2") {
		return URLTypeStatic
	}

	return URLTypePage
}

// GetResults returns all crawled results
func (c *Crawler) GetResults() []Result {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.results
}

// GetAPIEndpoints returns only API endpoints
func (c *Crawler) GetAPIEndpoints() []Result {
	c.mu.RLock()
	defer c.mu.RUnlock()

	var apis []Result
	for _, r := range c.results {
		if r.Type == URLTypeAPI {
			apis = append(apis, r)
		}
	}
	return apis
}

// GetForms returns all discovered forms
func (c *Crawler) GetForms() []Form {
	c.mu.RLock()
	defer c.mu.RUnlock()

	var forms []Form
	for _, r := range c.results {
		forms = append(forms, r.Forms...)
	}
	return forms
}
