// Package requester provides high-performance HTTP request functionality.
package requester

import (
	"crypto/tls"
	"time"

	"github.com/valyala/fasthttp"
)

// Client wraps fasthttp.Client with convenience methods
type Client struct {
	client    *fasthttp.Client
	timeout   time.Duration
	userAgent string
}

// ClientOptions configures the HTTP client
type ClientOptions struct {
	Timeout             time.Duration
	MaxConnsPerHost     int
	MaxIdleConnDuration time.Duration
	UserAgent           string
	SkipTLSVerify       bool
}

// DefaultClientOptions returns sensible defaults
func DefaultClientOptions() *ClientOptions {
	return &ClientOptions{
		Timeout:             10 * time.Second,
		MaxConnsPerHost:     500,
		MaxIdleConnDuration: 10 * time.Second,
		UserAgent:           "FluxFuzzer/1.0",
		SkipTLSVerify:       true,
	}
}

// NewClient creates a new HTTP client
func NewClient(opts *ClientOptions) *Client {
	if opts == nil {
		opts = DefaultClientOptions()
	}

	client := &fasthttp.Client{
		MaxConnsPerHost:     opts.MaxConnsPerHost,
		MaxIdleConnDuration: opts.MaxIdleConnDuration,
		ReadTimeout:         opts.Timeout,
		WriteTimeout:        opts.Timeout,
		TLSConfig: &tls.Config{
			InsecureSkipVerify: opts.SkipTLSVerify,
		},
	}

	return &Client{
		client:    client,
		timeout:   opts.Timeout,
		userAgent: opts.UserAgent,
	}
}

// Request represents an HTTP request to be sent
type Request struct {
	Method  string
	URL     string
	Headers map[string]string
	Body    []byte
}

// Response represents an HTTP response
type Response struct {
	StatusCode   int
	Headers      map[string]string
	Body         []byte
	ResponseTime time.Duration
	Error        error
}

// Do sends an HTTP request and returns the response
func (c *Client) Do(req *Request) *Response {
	start := time.Now()

	frequest := fasthttp.AcquireRequest()
	fresponse := fasthttp.AcquireResponse()
	defer fasthttp.ReleaseRequest(frequest)
	defer fasthttp.ReleaseResponse(fresponse)

	// Set request details
	frequest.SetRequestURI(req.URL)
	frequest.Header.SetMethod(req.Method)
	frequest.Header.SetUserAgent(c.userAgent)

	// Set headers
	for key, value := range req.Headers {
		frequest.Header.Set(key, value)
	}

	// Set body
	if len(req.Body) > 0 {
		frequest.SetBody(req.Body)
	}

	// Send request
	err := c.client.DoTimeout(frequest, fresponse, c.timeout)
	responseTime := time.Since(start)

	if err != nil {
		return &Response{
			Error:        err,
			ResponseTime: responseTime,
		}
	}

	// Copy headers
	headers := make(map[string]string)
	fresponse.Header.VisitAll(func(key, value []byte) {
		headers[string(key)] = string(value)
	})

	// Copy body (important: must copy as buffer is reused)
	body := make([]byte, len(fresponse.Body()))
	copy(body, fresponse.Body())

	return &Response{
		StatusCode:   fresponse.StatusCode(),
		Headers:      headers,
		Body:         body,
		ResponseTime: responseTime,
	}
}
