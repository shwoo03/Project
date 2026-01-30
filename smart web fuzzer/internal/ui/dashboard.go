// Package ui provides a TUI dashboard for FluxFuzzer.
package ui

import (
	"fmt"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Status represents the dashboard state
type Status int

const (
	StatusIdle Status = iota
	StatusRunning
	StatusPaused
	StatusStopped
	StatusCompleted
)

func (s Status) String() string {
	switch s {
	case StatusIdle:
		return "Idle"
	case StatusRunning:
		return "Running"
	case StatusPaused:
		return "Paused"
	case StatusStopped:
		return "Stopped"
	case StatusCompleted:
		return "Completed"
	default:
		return "Unknown"
	}
}

// LogEntry represents a log message
type LogEntry struct {
	Time    time.Time
	Level   string
	Message string
}

// Dashboard is the main TUI model
type Dashboard struct {
	// Dimensions
	width  int
	height int

	// State
	status    Status
	stats     *Stats
	statsView *StatsView
	progress  *ProgressView
	spinner   *SpinnerProgress

	// Logs
	logs    []LogEntry
	maxLogs int

	// Target info
	targetURL string

	// Animation
	tickCount int
}

// NewDashboard creates a new dashboard instance
func NewDashboard() *Dashboard {
	return &Dashboard{
		width:     80,
		height:    24,
		status:    StatusIdle,
		stats:     NewStats(),
		statsView: NewStatsView(40, 15),
		progress:  NewProgressView(70),
		spinner:   NewSpinnerProgress(),
		logs:      make([]LogEntry, 0, 100),
		maxLogs:   50,
	}
}

// SetTargetURL sets the target URL to display
func (d *Dashboard) SetTargetURL(url string) {
	d.targetURL = url
}

// AddLog adds a log entry
func (d *Dashboard) AddLog(level, message string) {
	entry := LogEntry{
		Time:    time.Now(),
		Level:   level,
		Message: message,
	}

	d.logs = append(d.logs, entry)

	// Trim if too many logs
	if len(d.logs) > d.maxLogs {
		d.logs = d.logs[len(d.logs)-d.maxLogs:]
	}
}

// GetStats returns the stats for external updates
func (d *Dashboard) GetStats() *Stats {
	return d.stats
}

// Start starts the fuzzing
func (d *Dashboard) Start() {
	d.status = StatusRunning
	d.spinner.Start()
	d.AddLog("INFO", "Fuzzing started")
}

// Pause pauses the fuzzing
func (d *Dashboard) Pause() {
	d.status = StatusPaused
	d.spinner.Stop()
	d.AddLog("INFO", "Fuzzing paused")
}

// Resume resumes the fuzzing
func (d *Dashboard) Resume() {
	d.status = StatusRunning
	d.spinner.Start()
	d.AddLog("INFO", "Fuzzing resumed")
}

// Stop stops the fuzzing
func (d *Dashboard) Stop() {
	d.status = StatusStopped
	d.spinner.Stop()
	d.AddLog("INFO", "Fuzzing stopped")
}

// Complete marks fuzzing as complete
func (d *Dashboard) Complete() {
	d.status = StatusCompleted
	d.spinner.Stop()
	d.AddLog("INFO", "Fuzzing completed")
}

// --- Bubbletea Model interface ---

// TickMsg is sent on each animation tick
type TickMsg time.Time

// StatsUpdateMsg is sent when stats should be updated
type StatsUpdateMsg struct{}

// Init initializes the model
func (d *Dashboard) Init() tea.Cmd {
	return tea.Batch(
		tickCmd(),
		tea.EnterAltScreen,
	)
}

// tickCmd returns a command that ticks periodically
func tickCmd() tea.Cmd {
	return tea.Tick(100*time.Millisecond, func(t time.Time) tea.Msg {
		return TickMsg(t)
	})
}

// Update handles messages
func (d *Dashboard) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c":
			return d, tea.Quit
		case "p":
			if d.status == StatusRunning {
				d.Pause()
			} else if d.status == StatusPaused {
				d.Resume()
			}
		case "r":
			if d.status == StatusPaused || d.status == StatusStopped {
				d.Resume()
			}
		case "s":
			if d.status == StatusRunning || d.status == StatusPaused {
				d.Stop()
			}
		}

	case tea.WindowSizeMsg:
		d.width = msg.Width
		d.height = msg.Height
		d.statsView.SetSize(d.width/3, d.height-10)
		d.progress.SetSize(d.width - 4)

	case TickMsg:
		d.tickCount++
		d.spinner.Tick()

		// Update progress view
		snap := d.stats.Snapshot()
		eta := formatDuration(snap.ETA)
		d.progress.Update(snap.CompletedTargets, snap.TotalTargets, eta)

		return d, tickCmd()
	}

	return d, nil
}

// View renders the dashboard
func (d *Dashboard) View() string {
	if d.width == 0 {
		return "Loading..."
	}

	var b strings.Builder

	// Header
	b.WriteString(d.renderHeader())
	b.WriteString("\n")

	// Main content area
	mainContent := lipgloss.JoinHorizontal(
		lipgloss.Top,
		d.renderStatsPanel(),
		d.renderLogPanel(),
	)
	b.WriteString(mainContent)
	b.WriteString("\n")

	// Progress bar
	b.WriteString(d.renderProgress())
	b.WriteString("\n")

	// Footer
	b.WriteString(d.renderFooter())

	return b.String()
}

// renderHeader renders the header section
func (d *Dashboard) renderHeader() string {
	// Title
	title := TitleStyle.Render("⚡ FluxFuzzer")

	// Status
	var statusText string
	switch d.status {
	case StatusRunning:
		statusText = RunningStyle.Render("● RUNNING")
	case StatusPaused:
		statusText = PausedStyle.Render("⏸ PAUSED")
	case StatusStopped:
		statusText = StoppedStyle.Render("■ STOPPED")
	case StatusCompleted:
		statusText = SuccessStyle.Render("✓ COMPLETED")
	default:
		statusText = HelpStyle.Render("○ IDLE")
	}

	// Target
	target := ""
	if d.targetURL != "" {
		target = LabelStyle.Render("Target: ") + InfoStyle.Render(d.targetURL)
	}

	// Build header
	leftSide := title + "  " + statusText
	rightSide := target

	// Add padding
	padding := d.width - lipgloss.Width(leftSide) - lipgloss.Width(rightSide) - 2
	if padding < 0 {
		padding = 0
	}

	header := leftSide + strings.Repeat(" ", padding) + rightSide

	return BoxStyle.Width(d.width - 2).Render(header)
}

// renderStatsPanel renders the statistics panel
func (d *Dashboard) renderStatsPanel() string {
	snap := d.stats.Snapshot()
	return d.statsView.Render(snap)
}

// renderLogPanel renders the log panel
func (d *Dashboard) renderLogPanel() string {
	var b strings.Builder

	b.WriteString(HeaderStyle.Render("📝 Activity Log"))
	b.WriteString("\n\n")

	// Show recent logs
	startIdx := 0
	if len(d.logs) > 8 {
		startIdx = len(d.logs) - 8
	}

	for i := startIdx; i < len(d.logs); i++ {
		log := d.logs[i]

		timeStr := log.Time.Format("15:04:05")

		var levelStyle lipgloss.Style
		switch log.Level {
		case "ERROR":
			levelStyle = ErrorStyle
		case "WARN":
			levelStyle = WarningStyle
		case "INFO":
			levelStyle = InfoStyle
		default:
			levelStyle = HelpStyle
		}

		line := fmt.Sprintf("%s %s %s",
			HelpStyle.Render(timeStr),
			levelStyle.Render(fmt.Sprintf("%-5s", log.Level)),
			log.Message,
		)

		// Truncate if too long
		if len(line) > d.width/2-10 {
			line = line[:d.width/2-13] + "..."
		}

		b.WriteString(line)
		b.WriteString("\n")
	}

	return LogPanelStyle.Width(d.width/2 - 4).Render(b.String())
}

// renderProgress renders the progress section
func (d *Dashboard) renderProgress() string {
	return d.progress.Render()
}

// renderFooter renders the footer with help text
func (d *Dashboard) renderFooter() string {
	var helps []string

	if d.status == StatusRunning {
		helps = append(helps, RenderHelp("p", "pause"))
		helps = append(helps, RenderHelp("s", "stop"))
	} else if d.status == StatusPaused {
		helps = append(helps, RenderHelp("r", "resume"))
		helps = append(helps, RenderHelp("s", "stop"))
	} else if d.status == StatusStopped || d.status == StatusIdle {
		helps = append(helps, RenderHelp("r", "start"))
	}

	helps = append(helps, RenderHelp("q", "quit"))

	return FooterStyle.Render(strings.Join(helps, "  "))
}

// Run starts the TUI application
func Run(d *Dashboard) error {
	p := tea.NewProgram(d, tea.WithAltScreen())
	_, err := p.Run()
	return err
}

// RunWithProgram returns the tea.Program for external control
func RunWithProgram(d *Dashboard) *tea.Program {
	return tea.NewProgram(d, tea.WithAltScreen())
}
