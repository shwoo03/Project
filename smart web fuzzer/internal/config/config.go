// Package config handles configuration loading and management for FluxFuzzer.
package config

import (
	"time"
)

// Config represents the global configuration for FluxFuzzer
type Config struct {
	Target   TargetConfig   `yaml:"target"`
	Engine   EngineConfig   `yaml:"engine"`
	Analyzer AnalyzerConfig `yaml:"analyzer"`
	State    StateConfig    `yaml:"state"`
	Output   OutputConfig   `yaml:"output"`
}

// TargetConfig defines the target configuration
type TargetConfig struct {
	URL       string            `yaml:"url"`
	Method    string            `yaml:"method"`
	Headers   map[string]string `yaml:"headers"`
	Body      string            `yaml:"body"`
	Wordlists []string          `yaml:"wordlists"`
}

// EngineConfig defines the request engine configuration
type EngineConfig struct {
	Workers    int           `yaml:"workers"`
	RPS        int           `yaml:"rps"`
	Timeout    time.Duration `yaml:"timeout"`
	MaxRetries int           `yaml:"max_retries"`
	UserAgent  string        `yaml:"user_agent"`
}

// AnalyzerConfig defines the analyzer configuration
type AnalyzerConfig struct {
	StructureThreshold int     `yaml:"structure_threshold"`
	TimeThreshold      float64 `yaml:"time_threshold"`
	BaselineSamples    int     `yaml:"baseline_samples"`
	EnableSimHash      bool    `yaml:"enable_simhash"`
	EnableTLSH         bool    `yaml:"enable_tlsh"`
}

// StateConfig defines the state management configuration
type StateConfig struct {
	EnableExtraction bool     `yaml:"enable_extraction"`
	ExtractPatterns  []string `yaml:"extract_patterns"`
	PoolTTL          int      `yaml:"pool_ttl"`
}

// OutputConfig defines the output configuration
type OutputConfig struct {
	Format       string `yaml:"format"`        // json, html, markdown
	OutputFile   string `yaml:"output_file"`
	Verbose      bool   `yaml:"verbose"`
	EnableTUI    bool   `yaml:"enable_tui"`
	QuietMode    bool   `yaml:"quiet_mode"`
}

// DefaultConfig returns the default configuration
func DefaultConfig() *Config {
	return &Config{
		Target: TargetConfig{
			Method: "GET",
			Headers: map[string]string{
				"User-Agent": "FluxFuzzer/1.0",
			},
		},
		Engine: EngineConfig{
			Workers:    50,
			RPS:        100,
			Timeout:    10 * time.Second,
			MaxRetries: 3,
			UserAgent:  "FluxFuzzer/1.0",
		},
		Analyzer: AnalyzerConfig{
			StructureThreshold: 15,
			TimeThreshold:      2.5,
			BaselineSamples:    10,
			EnableSimHash:      true,
			EnableTLSH:         false,
		},
		State: StateConfig{
			EnableExtraction: true,
			PoolTTL:          3600,
		},
		Output: OutputConfig{
			Format:    "json",
			EnableTUI: true,
		},
	}
}
