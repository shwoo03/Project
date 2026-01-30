// Package report provides HTML report generation.
package report

import (
	"fmt"
	"html/template"
	"io"
	"time"
)

// HTMLGenerator generates HTML reports
type HTMLGenerator struct {
	template *template.Template
}

// NewHTMLGenerator creates a new HTML generator
func NewHTMLGenerator() *HTMLGenerator {
	tmpl := template.Must(template.New("report").Funcs(template.FuncMap{
		"severityClass": func(s Severity) string {
			switch s {
			case SeverityCritical:
				return "critical"
			case SeverityHigh:
				return "high"
			case SeverityMedium:
				return "medium"
			case SeverityLow:
				return "low"
			default:
				return "info"
			}
		},
		"formatTime": func(t time.Time) string {
			return t.Format("2006-01-02 15:04:05")
		},
		"formatDuration": func(d time.Duration) string {
			return d.String()
		},
		"truncate": func(s string, n int) string {
			if len(s) <= n {
				return s
			}
			return s[:n] + "..."
		},
	}).Parse(htmlTemplate))

	return &HTMLGenerator{
		template: tmpl,
	}
}

// Generate generates an HTML report
func (g *HTMLGenerator) Generate(report *Report, w io.Writer) error {
	return g.template.Execute(w, report)
}

// Extension returns the file extension
func (g *HTMLGenerator) Extension() string {
	return "html"
}

const htmlTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{.Title}} - FluxFuzzer Report</title>
    <style>
        :root {
            --bg-dark: #0D0D0D;
            --bg-panel: #1A1A2E;
            --bg-header: #16213E;
            --text-primary: #E0E0E0;
            --text-dim: #666666;
            --cyan: #00FFFF;
            --magenta: #FF00FF;
            --green: #00FF00;
            --yellow: #FFFF00;
            --red: #FF0055;
            --orange: #FF8800;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            background: var(--bg-header);
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            border: 1px solid var(--cyan);
        }
        
        h1 {
            color: var(--cyan);
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 0 0 10px var(--cyan);
        }
        
        .meta {
            color: var(--text-dim);
            font-size: 0.9em;
        }
        
        .meta span {
            margin-right: 20px;
        }
        
        .section {
            background: var(--bg-panel);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid var(--magenta);
        }
        
        h2 {
            color: var(--magenta);
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .stat-card {
            background: var(--bg-header);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid var(--cyan);
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: var(--cyan);
        }
        
        .stat-label {
            color: var(--text-dim);
            font-size: 0.9em;
            margin-top: 5px;
        }
        
        .severity-badges {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        
        .badge {
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .badge.critical { background: var(--red); color: white; }
        .badge.high { background: var(--orange); color: white; }
        .badge.medium { background: var(--yellow); color: black; }
        .badge.low { background: var(--green); color: black; }
        .badge.info { background: var(--cyan); color: black; }
        
        .anomaly-list {
            list-style: none;
        }
        
        .anomaly-item {
            background: var(--bg-header);
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 8px;
            border-left: 4px solid var(--cyan);
        }
        
        .anomaly-item.critical { border-left-color: var(--red); }
        .anomaly-item.high { border-left-color: var(--orange); }
        .anomaly-item.medium { border-left-color: var(--yellow); }
        .anomaly-item.low { border-left-color: var(--green); }
        
        .anomaly-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .anomaly-title {
            font-weight: bold;
            color: var(--text-primary);
        }
        
        .anomaly-meta {
            color: var(--text-dim);
            font-size: 0.8em;
        }
        
        .anomaly-details {
            font-size: 0.9em;
        }
        
        .anomaly-details code {
            background: var(--bg-dark);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Fira Code', 'Consolas', monospace;
            color: var(--cyan);
        }
        
        .no-anomalies {
            text-align: center;
            padding: 40px;
            color: var(--green);
            font-size: 1.2em;
        }
        
        footer {
            text-align: center;
            color: var(--text-dim);
            padding: 20px;
            font-size: 0.9em;
        }
        
        footer a {
            color: var(--cyan);
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚡ {{.Title}}</h1>
            <div class="meta">
                <span>🎯 Target: <strong>{{.TargetURL}}</strong></span>
                <span>📅 Generated: {{formatTime .GeneratedAt}}</span>
                <span>📌 Version: {{.Version}}</span>
            </div>
        </header>
        
        <section class="section">
            <h2>📊 Statistics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{{.Statistics.TotalRequests}}</div>
                    <div class="stat-label">Total Requests</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{.Statistics.SuccessCount}}</div>
                    <div class="stat-label">Success</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{.Statistics.FailureCount}}</div>
                    <div class="stat-label">Failures</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{printf "%.1f" .Statistics.RequestsPerSec}}</div>
                    <div class="stat-label">Requests/sec</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{formatDuration .Statistics.Duration}}</div>
                    <div class="stat-label">Duration</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{formatDuration .Statistics.AvgResponseTime}}</div>
                    <div class="stat-label">Avg Response</div>
                </div>
            </div>
        </section>
        
        <section class="section">
            <h2>🔍 Anomalies ({{len .Anomalies}})</h2>
            
            {{if .Anomalies}}
            <div class="severity-badges">
                {{range $sev, $count := .SeverityCounts}}
                {{if gt $count 0}}
                <span class="badge {{severityClass $sev}}">{{$sev}}: {{$count}}</span>
                {{end}}
                {{end}}
            </div>
            
            <ul class="anomaly-list">
                {{range .Anomalies}}
                <li class="anomaly-item {{severityClass .Severity}}">
                    <div class="anomaly-header">
                        <span class="anomaly-title">{{.Description}}</span>
                        <span class="badge {{severityClass .Severity}}">{{.Severity}}</span>
                    </div>
                    <div class="anomaly-details">
                        <p><strong>Type:</strong> {{.Type}}</p>
                        <p><strong>URL:</strong> <code>{{.Method}} {{.URL}}</code></p>
                        {{if .Payload}}
                        <p><strong>Payload:</strong> <code>{{truncate .Payload 100}}</code></p>
                        {{end}}
                        {{if .StatusCode}}
                        <p><strong>Status Code:</strong> {{.StatusCode}}</p>
                        {{end}}
                    </div>
                    <div class="anomaly-meta">{{formatTime .Timestamp}}</div>
                </li>
                {{end}}
            </ul>
            {{else}}
            <div class="no-anomalies">
                ✅ No anomalies detected!
            </div>
            {{end}}
        </section>
        
        <footer>
            Generated by <a href="#">FluxFuzzer</a> - Smart Web Fuzzer
        </footer>
    </div>
</body>
</html>`

// SetTemplate sets a custom template
func (g *HTMLGenerator) SetTemplate(tmpl *template.Template) {
	g.template = tmpl
}

// GetDefaultTemplate returns the default HTML template string
func GetDefaultTemplate() string {
	return htmlTemplate
}

// CustomHTMLGenerator creates a generator with a custom template
func CustomHTMLGenerator(templateStr string) (*HTMLGenerator, error) {
	tmpl, err := template.New("report").Funcs(template.FuncMap{
		"severityClass": func(s Severity) string {
			switch s {
			case SeverityCritical:
				return "critical"
			case SeverityHigh:
				return "high"
			case SeverityMedium:
				return "medium"
			case SeverityLow:
				return "low"
			default:
				return "info"
			}
		},
		"formatTime": func(t time.Time) string {
			return t.Format("2006-01-02 15:04:05")
		},
		"formatDuration": func(d time.Duration) string {
			return d.String()
		},
		"truncate": func(s string, n int) string {
			if len(s) <= n {
				return s
			}
			return s[:n] + "..."
		},
	}).Parse(templateStr)

	if err != nil {
		return nil, fmt.Errorf("failed to parse template: %w", err)
	}

	return &HTMLGenerator{template: tmpl}, nil
}
