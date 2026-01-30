// Package web provides the web dashboard server for FluxFuzzer.
package web

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/url"
	"sync"
	"time"

	"github.com/fluxfuzzer/fluxfuzzer/internal/owasp"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/websocket/v2"
	"golang.org/x/time/rate"
)

// Server represents the web dashboard server
type Server struct {
	app       *fiber.App
	stats     *FuzzerStats
	mu        sync.RWMutex
	clients   map[*websocket.Conn]bool
	clientsMu sync.Mutex
	broadcast chan []byte
}

// FuzzerStats holds real-time fuzzing statistics
type FuzzerStats struct {
	IsRunning       bool      `json:"isRunning"`
	TargetURL       string    `json:"targetUrl"`
	StartTime       time.Time `json:"startTime"`
	TotalRequests   int64     `json:"totalRequests"`
	SuccessRequests int64     `json:"successRequests"`
	FailedRequests  int64     `json:"failedRequests"`
	RequestsPerSec  float64   `json:"requestsPerSec"`
	AnomaliesFound  int64     `json:"anomaliesFound"`
	CurrentPayload  string    `json:"currentPayload"`
	ElapsedTime     string    `json:"elapsedTime"`
	Workers         int       `json:"workers"`
}

// RequestLog represents a single request log entry
type RequestLog struct {
	ID           string    `json:"id"`
	Timestamp    time.Time `json:"timestamp"`
	Method       string    `json:"method"`
	URL          string    `json:"url"`
	StatusCode   int       `json:"statusCode"`
	ResponseTime int64     `json:"responseTime"` // milliseconds
	BodyLength   int       `json:"bodyLength"`
	IsAnomaly    bool      `json:"isAnomaly"`
	Payload      string    `json:"payload"`
}

// AnomalyLog represents a detected anomaly
type AnomalyLog struct {
	ID          string    `json:"id"`
	Timestamp   time.Time `json:"timestamp"`
	URL         string    `json:"url"`
	Payload     string    `json:"payload"`
	Reason      string    `json:"reason"`
	Severity    string    `json:"severity"`
	Distance    int       `json:"distance"`
	TimeSkew    float64   `json:"timeSkew"`
	StatusCode  int       `json:"statusCode"`
	Type        string    `json:"type"`
	Description string    `json:"description"`
	Remediation string    `json:"remediation"`
}

// NewServer creates a new web dashboard server
func NewServer() *Server {
	app := fiber.New(fiber.Config{
		DisableStartupMessage: true,
	})

	server := &Server{
		app:       app,
		stats:     &FuzzerStats{},
		clients:   make(map[*websocket.Conn]bool),
		broadcast: make(chan []byte, 100),
	}

	server.setupRoutes()
	go server.handleBroadcast()

	return server
}

// setupRoutes configures all HTTP routes
func (s *Server) setupRoutes() {
	// Enable CORS
	s.app.Use(cors.New())

	// API routes
	api := s.app.Group("/api")

	// Stats endpoint
	api.Get("/stats", s.handleStats)

	// Control endpoints
	api.Post("/start", s.handleStart)
	api.Post("/stop", s.handleStop)
	api.Post("/config", s.handleConfig)

	// Logs endpoint
	api.Get("/logs", s.handleLogs)
	api.Get("/anomalies", s.handleAnomalies)

	// WebSocket for real-time updates
	s.app.Use("/ws", func(c *fiber.Ctx) error {
		if websocket.IsWebSocketUpgrade(c) {
			return c.Next()
		}
		return fiber.ErrUpgradeRequired
	})
	s.app.Get("/ws", websocket.New(s.handleWebSocket))

	// Serve static files (embedded dashboard)
	s.app.Get("/", s.handleDashboard)
	s.app.Get("/dashboard.js", s.handleDashboardJS)
	s.app.Get("/dashboard.css", s.handleDashboardCSS)
}

// handleStats returns current fuzzing statistics
func (s *Server) handleStats(c *fiber.Ctx) error {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return c.JSON(s.stats)
}

// handleStart starts the fuzzing process
func (s *Server) handleStart(c *fiber.Ctx) error {
	var req struct {
		TargetURL string `json:"targetUrl"`
		Wordlist  string `json:"wordlist"`
		Workers   int    `json:"workers"`
		RPS       int    `json:"rps"`
	}

	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}

	s.mu.Lock()
	if s.stats.IsRunning {
		s.mu.Unlock()
		return c.Status(400).JSON(fiber.Map{"error": "Fuzzing is already running"})
	}
	s.stats.IsRunning = true
	s.stats.TargetURL = req.TargetURL
	s.stats.StartTime = time.Now()
	s.stats.Workers = req.Workers
	s.stats.TotalRequests = 0
	s.stats.SuccessRequests = 0
	s.stats.FailedRequests = 0
	s.stats.AnomaliesFound = 0
	s.mu.Unlock()
	s.BroadcastStats()

	// Start fuzzing engine in goroutine
	go func() {
		defer func() {
			s.mu.Lock()
			s.stats.IsRunning = false
			s.mu.Unlock()
			s.BroadcastStats()
		}()

		detector := owasp.NewDetector(nil)

		// Parse URL
		u, err := url.Parse(req.TargetURL)
		params := make(map[string]string)
		if err == nil {
			for k, v := range u.Query() {
				if len(v) > 0 {
					params[k] = v[0]
				}
			}
		}

		target := &owasp.Target{
			URL:        req.TargetURL,
			Method:     "GET",
			Parameters: params,
		}

		// 10 minutes timeout
		ctx, cancel := context.WithTimeout(context.Background(), 600*time.Second)

		// Rate Limiter Setup
		if req.RPS > 0 {
			limiter := rate.NewLimiter(rate.Limit(req.RPS), 1)
			ctx = owasp.WithRateLimiter(ctx, limiter)
		}

		defer cancel()

		findings, err := detector.Scan(ctx, target)

		s.mu.Lock()
		s.stats.AnomaliesFound = int64(len(findings))
		stats := detector.GetStats()
		s.stats.TotalRequests = stats.TotalChecks
		s.mu.Unlock()
		s.BroadcastStats()

		if err != nil {
			log.Printf("Scan error: %v", err)
		}

		// Broadcast findings
		for _, f := range findings {
			anomaly := &AnomalyLog{
				ID:          fmt.Sprintf("%d", time.Now().UnixNano()),
				Timestamp:   f.Timestamp,
				URL:         f.URL,
				Payload:     f.Payload,
				Reason:      fmt.Sprintf("[%s] %s", f.Type, f.Description),
				Type:        string(f.Type),
				Description: f.Description,
				Remediation: f.Remediation,
				Severity:    string(f.Severity),
				StatusCode:  200,
			}
			s.BroadcastAnomaly(anomaly)
		}
	}()

	return c.JSON(fiber.Map{"status": "started"})
}

// handleStop stops the fuzzing process
func (s *Server) handleStop(c *fiber.Ctx) error {
	s.mu.Lock()
	s.stats.IsRunning = false
	s.mu.Unlock()

	// TODO: Actually stop the fuzzing engine here

	return c.JSON(fiber.Map{"status": "stopped"})
}

// handleConfig updates fuzzer configuration
func (s *Server) handleConfig(c *fiber.Ctx) error {
	// TODO: Handle configuration updates
	return c.JSON(fiber.Map{"status": "updated"})
}

// handleLogs returns recent request logs
func (s *Server) handleLogs(c *fiber.Ctx) error {
	// TODO: Return actual logs from fuzzing engine
	logs := []RequestLog{}
	return c.JSON(logs)
}

// handleAnomalies returns detected anomalies
func (s *Server) handleAnomalies(c *fiber.Ctx) error {
	// TODO: Return actual anomalies from analyzer
	anomalies := []AnomalyLog{}
	return c.JSON(anomalies)
}

// handleWebSocket handles WebSocket connections for real-time updates
func (s *Server) handleWebSocket(c *websocket.Conn) {
	s.clientsMu.Lock()
	s.clients[c] = true
	s.clientsMu.Unlock()

	defer func() {
		s.clientsMu.Lock()
		delete(s.clients, c)
		s.clientsMu.Unlock()
		c.Close()
	}()

	// Send initial stats
	s.mu.RLock()
	data, _ := json.Marshal(map[string]interface{}{
		"type": "stats",
		"data": s.stats,
	})
	s.mu.RUnlock()
	c.WriteMessage(websocket.TextMessage, data)

	// Keep connection alive
	for {
		_, _, err := c.ReadMessage()
		if err != nil {
			break
		}
	}
}

// handleBroadcast sends updates to all connected clients
func (s *Server) handleBroadcast() {
	for msg := range s.broadcast {
		s.clientsMu.Lock()
		for client := range s.clients {
			if err := client.WriteMessage(websocket.TextMessage, msg); err != nil {
				client.Close()
				delete(s.clients, client)
			}
		}
		s.clientsMu.Unlock()
	}
}

// BroadcastStats sends stats update to all connected clients
func (s *Server) BroadcastStats() {
	s.mu.RLock()
	data, _ := json.Marshal(map[string]interface{}{
		"type": "stats",
		"data": s.stats,
	})
	s.mu.RUnlock()

	select {
	case s.broadcast <- data:
	default:
		// Channel full, skip this update
	}
}

// BroadcastLog sends a request log to all connected clients
func (s *Server) BroadcastLog(log *RequestLog) {
	data, _ := json.Marshal(map[string]interface{}{
		"type": "log",
		"data": log,
	})

	select {
	case s.broadcast <- data:
	default:
	}
}

// BroadcastAnomaly sends an anomaly alert to all connected clients
func (s *Server) BroadcastAnomaly(anomaly *AnomalyLog) {
	data, _ := json.Marshal(map[string]interface{}{
		"type": "anomaly",
		"data": anomaly,
	})

	select {
	case s.broadcast <- data:
	default:
	}
}

// UpdateStats updates the statistics (called by fuzzing engine)
func (s *Server) UpdateStats(total, success, failed, anomalies int64, rps float64, payload string) {
	s.mu.Lock()
	s.stats.TotalRequests = total
	s.stats.SuccessRequests = success
	s.stats.FailedRequests = failed
	s.stats.AnomaliesFound = anomalies
	s.stats.RequestsPerSec = rps
	s.stats.CurrentPayload = payload
	if s.stats.IsRunning {
		s.stats.ElapsedTime = time.Since(s.stats.StartTime).Round(time.Second).String()
	}
	s.mu.Unlock()

	s.BroadcastStats()
}

// Start starts the web server
func (s *Server) Start(addr string) error {
	log.Printf("[*] Web Dashboard starting at http://localhost%s\n", addr)
	return s.app.Listen(addr)
}

// Stop stops the web server
func (s *Server) Stop() error {
	return s.app.Shutdown()
}
