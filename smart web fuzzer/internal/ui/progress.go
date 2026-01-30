// Package ui provides progress bar components.
package ui

import (
	"fmt"
	"strings"
)

// ProgressBar represents a progress bar component
type ProgressBar struct {
	width      int
	percentage float64
	showETA    bool
	eta        string
	label      string
}

// NewProgressBar creates a new progress bar
func NewProgressBar(width int) *ProgressBar {
	return &ProgressBar{
		width:   width,
		showETA: true,
	}
}

// SetProgress sets the progress percentage (0.0 to 1.0)
func (p *ProgressBar) SetProgress(percentage float64) {
	if percentage < 0 {
		percentage = 0
	}
	if percentage > 1 {
		percentage = 1
	}
	p.percentage = percentage
}

// SetETA sets the estimated time remaining
func (p *ProgressBar) SetETA(eta string) {
	p.eta = eta
}

// SetLabel sets the progress label
func (p *ProgressBar) SetLabel(label string) {
	p.label = label
}

// SetWidth sets the progress bar width
func (p *ProgressBar) SetWidth(width int) {
	p.width = width
}

// ShowETA enables/disables ETA display
func (p *ProgressBar) ShowETA(show bool) {
	p.showETA = show
}

// Render renders the progress bar
func (p *ProgressBar) Render() string {
	var b strings.Builder

	// Calculate bar width (accounting for percentage and brackets)
	barWidth := p.width - 10 // Reserve space for percentage and brackets
	if barWidth < 10 {
		barWidth = 10
	}

	filled := int(float64(barWidth) * p.percentage)
	empty := barWidth - filled

	// Build the progress bar
	b.WriteString(ProgressFullStyle.Render("█"))

	// Filled portion
	for i := 0; i < filled; i++ {
		b.WriteString(ProgressFullStyle.Render("█"))
	}

	// Empty portion
	for i := 0; i < empty; i++ {
		b.WriteString(ProgressEmptyStyle.Render("░"))
	}

	b.WriteString(ProgressEmptyStyle.Render("░"))

	// Percentage
	b.WriteString(" ")
	b.WriteString(ValueStyle.Render(fmt.Sprintf("%5.1f%%", p.percentage*100)))

	// ETA
	if p.showETA && p.eta != "" {
		b.WriteString(" ")
		b.WriteString(InfoStyle.Render("ETA: " + p.eta))
	}

	return b.String()
}

// RenderWithLabel renders the progress bar with a label
func (p *ProgressBar) RenderWithLabel() string {
	if p.label == "" {
		return p.Render()
	}
	return LabelStyle.Render(p.label) + "\n" + p.Render()
}

// ProgressView is a styled progress panel
type ProgressView struct {
	width     int
	progress  *ProgressBar
	title     string
	completed int64
	total     int64
}

// NewProgressView creates a new progress view
func NewProgressView(width int) *ProgressView {
	return &ProgressView{
		width:    width,
		progress: NewProgressBar(width - 6), // Account for panel padding
		title:    "Progress",
	}
}

// SetSize updates the view size
func (v *ProgressView) SetSize(width int) {
	v.width = width
	v.progress.SetWidth(width - 6)
}

// Update updates the progress view
func (v *ProgressView) Update(completed, total int64, eta string) {
	v.completed = completed
	v.total = total

	if total > 0 {
		v.progress.SetProgress(float64(completed) / float64(total))
	} else {
		v.progress.SetProgress(0)
	}

	v.progress.SetETA(eta)
}

// SetTitle sets the progress title
func (v *ProgressView) SetTitle(title string) {
	v.title = title
}

// Render renders the progress view
func (v *ProgressView) Render() string {
	var b strings.Builder

	// Title
	b.WriteString(HeaderStyle.Render("📈 " + v.title))
	b.WriteString("\n\n")

	// Progress bar
	b.WriteString(v.progress.Render())
	b.WriteString("\n\n")

	// Details
	if v.total > 0 {
		b.WriteString(RenderLabelValue("Completed", fmt.Sprintf("%d / %d", v.completed, v.total)))
	}

	return PanelStyle.Width(v.width).Render(b.String())
}

// SpinnerProgress shows an indeterminate progress with spinner
type SpinnerProgress struct {
	frame   int
	text    string
	running bool
}

// NewSpinnerProgress creates a new spinner progress
func NewSpinnerProgress() *SpinnerProgress {
	return &SpinnerProgress{
		text:    "Loading...",
		running: true,
	}
}

// SetText sets the spinner text
func (s *SpinnerProgress) SetText(text string) {
	s.text = text
}

// Start starts the spinner
func (s *SpinnerProgress) Start() {
	s.running = true
}

// Stop stops the spinner
func (s *SpinnerProgress) Stop() {
	s.running = false
}

// Tick advances the spinner animation
func (s *SpinnerProgress) Tick() {
	if s.running {
		s.frame = (s.frame + 1) % len(SpinnerChars)
	}
}

// Render renders the spinner
func (s *SpinnerProgress) Render() string {
	if !s.running {
		return SuccessStyle.Render("✓") + " " + s.text
	}
	return InfoStyle.Render(SpinnerChars[s.frame]) + " " + s.text
}
