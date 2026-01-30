// Package parallel provides backpressure handling utilities.
package parallel

import (
	"context"
	"sync"
	"sync/atomic"
	"time"
)

// BackpressureStrategy defines how to handle backpressure
type BackpressureStrategy int

const (
	StrategyBlock      BackpressureStrategy = iota // Block until space available
	StrategyDrop                                   // Drop new items when full
	StrategyDropOldest                             // Drop oldest items to make room
	StrategyAdaptive                               // Dynamically adjust rate
)

// BackpressureConfig holds backpressure configuration
type BackpressureConfig struct {
	Strategy      BackpressureStrategy
	MaxQueueSize  int
	HighWatermark float64 // Start slowing down
	LowWatermark  float64 // Resume normal speed
	MinRate       time.Duration
	MaxRate       time.Duration
}

// DefaultBackpressureConfig returns default configuration
func DefaultBackpressureConfig() *BackpressureConfig {
	return &BackpressureConfig{
		Strategy:      StrategyAdaptive,
		MaxQueueSize:  10000,
		HighWatermark: 0.8,
		LowWatermark:  0.5,
		MinRate:       1 * time.Millisecond,
		MaxRate:       100 * time.Millisecond,
	}
}

// BackpressureController manages backpressure
type BackpressureController struct {
	config      *BackpressureConfig
	currentRate int64 // nanoseconds
	isPressured int32
	stats       *BackpressureStats
	mu          sync.RWMutex
}

// BackpressureStats tracks backpressure statistics
type BackpressureStats struct {
	ItemsProcessed  int64
	ItemsDropped    int64
	ItemsBlocked    int64
	PressureEvents  int64
	CurrentPressure float64
	CurrentRateNs   int64
}

// NewBackpressureController creates a new controller
func NewBackpressureController(config *BackpressureConfig) *BackpressureController {
	if config == nil {
		config = DefaultBackpressureConfig()
	}

	return &BackpressureController{
		config:      config,
		currentRate: config.MinRate.Nanoseconds(),
		stats:       &BackpressureStats{},
	}
}

// CheckPressure checks current pressure level and returns whether to proceed
func (bc *BackpressureController) CheckPressure(queueLen, queueCap int) bool {
	if queueCap == 0 {
		return true
	}

	pressure := float64(queueLen) / float64(queueCap)
	bc.stats.CurrentPressure = pressure

	if pressure > bc.config.HighWatermark {
		// High pressure
		if atomic.CompareAndSwapInt32(&bc.isPressured, 0, 1) {
			atomic.AddInt64(&bc.stats.PressureEvents, 1)
		}
		bc.adjustRate(true)
		return bc.handleHighPressure()
	}

	if pressure < bc.config.LowWatermark {
		// Low pressure, resume normal
		atomic.StoreInt32(&bc.isPressured, 0)
		bc.adjustRate(false)
	}

	return true
}

// handleHighPressure handles high pressure based on strategy
func (bc *BackpressureController) handleHighPressure() bool {
	switch bc.config.Strategy {
	case StrategyBlock:
		// Block - return false to signal caller to wait
		atomic.AddInt64(&bc.stats.ItemsBlocked, 1)
		return false

	case StrategyDrop:
		// Drop new items
		atomic.AddInt64(&bc.stats.ItemsDropped, 1)
		return false

	case StrategyDropOldest:
		// Signal that oldest should be dropped
		return true

	case StrategyAdaptive:
		// Slow down but continue
		time.Sleep(time.Duration(atomic.LoadInt64(&bc.currentRate)))
		return true

	default:
		return true
	}
}

// adjustRate adjusts the processing rate
func (bc *BackpressureController) adjustRate(increase bool) {
	bc.mu.Lock()
	defer bc.mu.Unlock()

	current := atomic.LoadInt64(&bc.currentRate)
	maxRate := bc.config.MaxRate.Nanoseconds()
	minRate := bc.config.MinRate.Nanoseconds()

	if increase {
		// Increase delay (slow down)
		newRate := current * 2
		if newRate > maxRate {
			newRate = maxRate
		}
		atomic.StoreInt64(&bc.currentRate, newRate)
	} else {
		// Decrease delay (speed up)
		newRate := current / 2
		if newRate < minRate {
			newRate = minRate
		}
		atomic.StoreInt64(&bc.currentRate, newRate)
	}

	bc.stats.CurrentRateNs = atomic.LoadInt64(&bc.currentRate)
}

// Wait waits according to current rate
func (bc *BackpressureController) Wait() {
	rate := atomic.LoadInt64(&bc.currentRate)
	if rate > 0 {
		time.Sleep(time.Duration(rate))
	}
}

// IsPressured returns whether system is under pressure
func (bc *BackpressureController) IsPressured() bool {
	return atomic.LoadInt32(&bc.isPressured) == 1
}

// GetStats returns backpressure statistics
func (bc *BackpressureController) GetStats() BackpressureStats {
	bc.mu.RLock()
	defer bc.mu.RUnlock()

	return BackpressureStats{
		ItemsProcessed:  atomic.LoadInt64(&bc.stats.ItemsProcessed),
		ItemsDropped:    atomic.LoadInt64(&bc.stats.ItemsDropped),
		ItemsBlocked:    atomic.LoadInt64(&bc.stats.ItemsBlocked),
		PressureEvents:  atomic.LoadInt64(&bc.stats.PressureEvents),
		CurrentPressure: bc.stats.CurrentPressure,
		CurrentRateNs:   atomic.LoadInt64(&bc.currentRate),
	}
}

// RecordProcessed records a processed item
func (bc *BackpressureController) RecordProcessed() {
	atomic.AddInt64(&bc.stats.ItemsProcessed, 1)
}

// RateLimiter provides rate limiting functionality
type RateLimiter struct {
	rate       time.Duration
	burst      int
	tokens     int64
	lastUpdate int64
	mu         sync.Mutex
}

// NewRateLimiter creates a new rate limiter
func NewRateLimiter(rate time.Duration, burst int) *RateLimiter {
	return &RateLimiter{
		rate:       rate,
		burst:      burst,
		tokens:     int64(burst),
		lastUpdate: time.Now().UnixNano(),
	}
}

// Allow checks if an action is allowed
func (rl *RateLimiter) Allow() bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now().UnixNano()
	elapsed := now - rl.lastUpdate
	rl.lastUpdate = now

	// Add tokens based on elapsed time
	tokensToAdd := elapsed / int64(rl.rate)
	rl.tokens += tokensToAdd
	if rl.tokens > int64(rl.burst) {
		rl.tokens = int64(rl.burst)
	}

	if rl.tokens > 0 {
		rl.tokens--
		return true
	}

	return false
}

// Wait waits until an action is allowed
func (rl *RateLimiter) Wait(ctx context.Context) error {
	for {
		if rl.Allow() {
			return nil
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(rl.rate):
			// Try again
		}
	}
}

// SetRate updates the rate
func (rl *RateLimiter) SetRate(rate time.Duration) {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	rl.rate = rate
}

// Throttle provides simple throttling
type Throttle struct {
	interval time.Duration
	last     int64
}

// NewThrottle creates a new throttle
func NewThrottle(interval time.Duration) *Throttle {
	return &Throttle{
		interval: interval,
		last:     0,
	}
}

// Allow returns true if enough time has passed since last call
func (t *Throttle) Allow() bool {
	now := time.Now().UnixNano()
	last := atomic.LoadInt64(&t.last)

	if now-last >= int64(t.interval) {
		if atomic.CompareAndSwapInt64(&t.last, last, now) {
			return true
		}
	}

	return false
}

// Wait waits until the throttle allows
func (t *Throttle) Wait() {
	for !t.Allow() {
		time.Sleep(t.interval / 10)
	}
}
