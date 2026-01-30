// Package report provides JSON report generation.
package report

import (
	"encoding/json"
	"io"
)

// JSONGenerator generates JSON reports
type JSONGenerator struct {
	Indent bool
}

// Generate generates a JSON report
func (g *JSONGenerator) Generate(report *Report, w io.Writer) error {
	encoder := json.NewEncoder(w)

	if g.Indent {
		encoder.SetIndent("", "  ")
	}

	return encoder.Encode(report)
}

// Extension returns the file extension
func (g *JSONGenerator) Extension() string {
	return "json"
}

// GenerateBytes generates JSON report as bytes
func (g *JSONGenerator) GenerateBytes(report *Report) ([]byte, error) {
	if g.Indent {
		return json.MarshalIndent(report, "", "  ")
	}
	return json.Marshal(report)
}
