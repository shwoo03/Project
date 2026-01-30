// Package crawler provides sitemap parsing functionality.
package crawler

import (
	"context"
	"encoding/xml"
	"io"
	"net/http"
	"strings"
	"time"
)

// SitemapURL represents a URL in a sitemap
type SitemapURL struct {
	Loc        string  `xml:"loc"`
	LastMod    string  `xml:"lastmod"`
	ChangeFreq string  `xml:"changefreq"`
	Priority   float64 `xml:"priority"`
}

// Sitemap represents a sitemap.xml
type Sitemap struct {
	URLs []SitemapURL `xml:"url"`
}

// SitemapIndex represents a sitemap index
type SitemapIndex struct {
	Sitemaps []struct {
		Loc     string `xml:"loc"`
		LastMod string `xml:"lastmod"`
	} `xml:"sitemap"`
}

// SitemapParser parses sitemaps
type SitemapParser struct {
	client  *http.Client
	timeout time.Duration
}

// NewSitemapParser creates a new sitemap parser
func NewSitemapParser() *SitemapParser {
	return &SitemapParser{
		client:  &http.Client{Timeout: 30 * time.Second},
		timeout: 30 * time.Second,
	}
}

// Parse parses a sitemap from a URL
func (p *SitemapParser) Parse(ctx context.Context, sitemapURL string) ([]SitemapURL, error) {
	// Fetch sitemap
	req, err := http.NewRequestWithContext(ctx, "GET", sitemapURL, nil)
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

	return p.ParseBytes(ctx, body, sitemapURL)
}

// ParseBytes parses sitemap from bytes
func (p *SitemapParser) ParseBytes(ctx context.Context, data []byte, baseURL string) ([]SitemapURL, error) {
	var urls []SitemapURL

	// Try parsing as sitemap index first
	var index SitemapIndex
	if err := xml.Unmarshal(data, &index); err == nil && len(index.Sitemaps) > 0 {
		// It's a sitemap index, parse each sub-sitemap
		for _, sm := range index.Sitemaps {
			subURLs, err := p.Parse(ctx, sm.Loc)
			if err != nil {
				continue
			}
			urls = append(urls, subURLs...)
		}
		return urls, nil
	}

	// Try parsing as regular sitemap
	var sitemap Sitemap
	if err := xml.Unmarshal(data, &sitemap); err == nil {
		return sitemap.URLs, nil
	}

	// Try parsing as plain text (one URL per line)
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line != "" && strings.HasPrefix(line, "http") {
			urls = append(urls, SitemapURL{Loc: line})
		}
	}

	return urls, nil
}

// DiscoverSitemaps attempts to discover sitemaps at common locations
func (p *SitemapParser) DiscoverSitemaps(ctx context.Context, baseURL string) []string {
	commonPaths := []string{
		"/sitemap.xml",
		"/sitemap_index.xml",
		"/sitemap1.xml",
		"/sitemap-index.xml",
		"/sitemaps/sitemap.xml",
		"/robots.txt",
	}

	// Ensure base URL doesn't have trailing slash
	baseURL = strings.TrimSuffix(baseURL, "/")

	var discovered []string
	for _, path := range commonPaths {
		url := baseURL + path

		req, err := http.NewRequestWithContext(ctx, "HEAD", url, nil)
		if err != nil {
			continue
		}
		req.Header.Set("User-Agent", "FluxFuzzer/1.0")

		resp, err := p.client.Do(req)
		if err != nil {
			continue
		}
		resp.Body.Close()

		if resp.StatusCode == 200 {
			if path == "/robots.txt" {
				// Parse robots.txt for sitemap references
				sitemaps := p.parseRobotsTxt(ctx, url)
				discovered = append(discovered, sitemaps...)
			} else {
				discovered = append(discovered, url)
			}
		}
	}

	return discovered
}

// parseRobotsTxt parses robots.txt for sitemap references
func (p *SitemapParser) parseRobotsTxt(ctx context.Context, robotsURL string) []string {
	req, err := http.NewRequestWithContext(ctx, "GET", robotsURL, nil)
	if err != nil {
		return nil
	}
	req.Header.Set("User-Agent", "FluxFuzzer/1.0")

	resp, err := p.client.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil
	}

	var sitemaps []string
	lines := strings.Split(string(body), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(strings.ToLower(line), "sitemap:") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				sitemaps = append(sitemaps, strings.TrimSpace(parts[1]))
			}
		}
	}

	return sitemaps
}

// FetchAllURLs fetches all URLs from discovered sitemaps
func (p *SitemapParser) FetchAllURLs(ctx context.Context, baseURL string) ([]SitemapURL, error) {
	sitemaps := p.DiscoverSitemaps(ctx, baseURL)

	var allURLs []SitemapURL
	seen := make(map[string]bool)

	for _, sm := range sitemaps {
		urls, err := p.Parse(ctx, sm)
		if err != nil {
			continue
		}

		for _, u := range urls {
			if !seen[u.Loc] {
				seen[u.Loc] = true
				allURLs = append(allURLs, u)
			}
		}
	}

	return allURLs, nil
}
