// Package ui provides TUI dashboard components for FluxFuzzer.
package ui

import "github.com/charmbracelet/lipgloss"

// Color palette - Cyberpunk theme
var (
	// Primary colors
	ColorCyan    = lipgloss.Color("#00FFFF")
	ColorMagenta = lipgloss.Color("#FF00FF")
	ColorGreen   = lipgloss.Color("#00FF00")
	ColorYellow  = lipgloss.Color("#FFFF00")
	ColorRed     = lipgloss.Color("#FF0055")
	ColorOrange  = lipgloss.Color("#FF8800")

	// Background colors
	ColorDarkBg   = lipgloss.Color("#0D0D0D")
	ColorPanelBg  = lipgloss.Color("#1A1A2E")
	ColorHeaderBg = lipgloss.Color("#16213E")

	// Text colors
	ColorText       = lipgloss.Color("#E0E0E0")
	ColorDimText    = lipgloss.Color("#666666")
	ColorBrightText = lipgloss.Color("#FFFFFF")
)

// Style definitions
var (
	// Base styles
	BaseStyle = lipgloss.NewStyle().
			Background(ColorDarkBg).
			Foreground(ColorText)

	// Header styles
	HeaderStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(ColorCyan).
			Background(ColorHeaderBg).
			Padding(0, 1).
			MarginBottom(1)

	TitleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(ColorMagenta).
			Background(ColorHeaderBg).
			Padding(0, 2)

	// Panel styles
	PanelStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorCyan).
			Padding(1, 2).
			MarginRight(1)

	StatsPanelStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorMagenta).
			Padding(1, 2)

	LogPanelStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorGreen).
			Padding(0, 1).
			Height(10)

	// Text styles
	LabelStyle = lipgloss.NewStyle().
			Foreground(ColorDimText).
			Width(15)

	ValueStyle = lipgloss.NewStyle().
			Foreground(ColorBrightText).
			Bold(true)

	SuccessStyle = lipgloss.NewStyle().
			Foreground(ColorGreen).
			Bold(true)

	ErrorStyle = lipgloss.NewStyle().
			Foreground(ColorRed).
			Bold(true)

	WarningStyle = lipgloss.NewStyle().
			Foreground(ColorYellow)

	InfoStyle = lipgloss.NewStyle().
			Foreground(ColorCyan)

	// Status indicators
	RunningStyle = lipgloss.NewStyle().
			Foreground(ColorGreen).
			Bold(true)

	PausedStyle = lipgloss.NewStyle().
			Foreground(ColorYellow).
			Bold(true)

	StoppedStyle = lipgloss.NewStyle().
			Foreground(ColorRed).
			Bold(true)

	// Footer styles
	FooterStyle = lipgloss.NewStyle().
			Foreground(ColorDimText).
			MarginTop(1)

	KeyStyle = lipgloss.NewStyle().
			Foreground(ColorCyan).
			Bold(true)

	HelpStyle = lipgloss.NewStyle().
			Foreground(ColorDimText)

	// Progress bar styles
	ProgressFullStyle = lipgloss.NewStyle().
				Foreground(ColorCyan)

	ProgressEmptyStyle = lipgloss.NewStyle().
				Foreground(ColorDimText)

	// Anomaly styles
	AnomalyHighStyle = lipgloss.NewStyle().
				Foreground(ColorRed).
				Bold(true)

	AnomalyMediumStyle = lipgloss.NewStyle().
				Foreground(ColorOrange)

	AnomalyLowStyle = lipgloss.NewStyle().
			Foreground(ColorYellow)

	// Box styles for layout
	BoxStyle = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder()).
			BorderForeground(ColorCyan)

	// Spinner chars for animation
	SpinnerChars = []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}
)

// Helper functions

// RenderLabel renders a label with consistent styling
func RenderLabel(label string) string {
	return LabelStyle.Render(label + ":")
}

// RenderValue renders a value with consistent styling
func RenderValue(value string) string {
	return ValueStyle.Render(value)
}

// RenderLabelValue renders a label-value pair
func RenderLabelValue(label, value string) string {
	return RenderLabel(label) + " " + RenderValue(value)
}

// RenderSuccess renders success text
func RenderSuccess(text string) string {
	return SuccessStyle.Render(text)
}

// RenderError renders error text
func RenderError(text string) string {
	return ErrorStyle.Render(text)
}

// RenderWarning renders warning text
func RenderWarning(text string) string {
	return WarningStyle.Render(text)
}

// RenderKey renders a keyboard key
func RenderKey(key string) string {
	return KeyStyle.Render("[" + key + "]")
}

// RenderHelp renders help text
func RenderHelp(key, description string) string {
	return RenderKey(key) + " " + HelpStyle.Render(description)
}

// ASCII Art Banner
const Banner = `
╔═══════════════════════════════════════════════════════════════╗
║  ███████╗██╗     ██╗   ██╗██╗  ██╗███████╗██╗   ██╗███████╗   ║
║  ██╔════╝██║     ██║   ██║╚██╗██╔╝██╔════╝██║   ██║╚══███╔╝   ║
║  █████╗  ██║     ██║   ██║ ╚███╔╝ █████╗  ██║   ██║  ███╔╝    ║
║  ██╔══╝  ██║     ██║   ██║ ██╔██╗ ██╔══╝  ██║   ██║ ███╔╝     ║
║  ██║     ███████╗╚██████╔╝██╔╝ ██╗██║     ╚██████╔╝███████╗   ║
║  ╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝      ╚═════╝ ╚══════╝   ║
║                                                               ║
║              [ Smart Web Fuzzer v1.0 ]                        ║
╚═══════════════════════════════════════════════════════════════╝`

// MiniBanner is a compact version
const MiniBanner = `┌─ FluxFuzzer ──────────────────────────────────────────────────┐`

// GetBannerStyled returns styled banner
func GetBannerStyled() string {
	return lipgloss.NewStyle().
		Foreground(ColorCyan).
		Bold(true).
		Render(MiniBanner)
}
