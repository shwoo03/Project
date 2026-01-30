package owasp

import (
	"context"

	"golang.org/x/time/rate"
)

type contextKey string

const rateLimiterKey contextKey = "rateLimiter"

// WithRateLimiter returns a new context with the given rate limiter
func WithRateLimiter(ctx context.Context, limiter *rate.Limiter) context.Context {
	return context.WithValue(ctx, rateLimiterKey, limiter)
}

// WaitRateLimit waits for the rate limiter if it exists in the context
func WaitRateLimit(ctx context.Context) error {
	if limiter, ok := ctx.Value(rateLimiterKey).(*rate.Limiter); ok {
		return limiter.Wait(ctx)
	}
	return nil
}
