// FluxFuzzer - Smart Stateful Web Fuzzer
// A coverage-guided & state-aware DAST for modern web applications

package main

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/fluxfuzzer/fluxfuzzer/internal/owasp"
	"github.com/fluxfuzzer/fluxfuzzer/internal/web"
	"github.com/spf13/cobra"
)

var (
	version = "0.1.0-dev"

	// CLI flags
	targetURL  string
	wordlist   string
	threads    int
	rps        int
	timeout    int
	configFile string
	outputFile string
	verbose    bool
	webMode    bool
	webPort    string
)

func main() {
	rootCmd := &cobra.Command{
		Use:   "fluxfuzzer",
		Short: "FluxFuzzer - Smart Stateful Web Fuzzer",
		Long: `FluxFuzzer is a smart, stateful web fuzzer that uses
coverage-guided and state-aware techniques for effective DAST.

Features:
  - Structural Differential Analysis (SimHash/TLSH)
  - Stateful Fuzzing (Producer-Consumer tracking)
  - High-performance async HTTP engine
  - Smart type-aware mutation
  - Web-based Dashboard`,
		Run: runFuzzer,
	}

	// Define flags
	rootCmd.Flags().StringVarP(&targetURL, "url", "u", "", "Target URL to fuzz")
	rootCmd.Flags().StringVarP(&wordlist, "wordlist", "w", "", "Path to wordlist file")
	rootCmd.Flags().IntVarP(&threads, "threads", "t", 50, "Number of concurrent threads")
	rootCmd.Flags().IntVarP(&rps, "rate", "r", 100, "Requests per second limit")
	rootCmd.Flags().IntVar(&timeout, "timeout", 10, "Request timeout in seconds")
	rootCmd.Flags().StringVarP(&configFile, "config", "c", "", "Path to config file (YAML)")
	rootCmd.Flags().StringVarP(&outputFile, "output", "o", "", "Output file path")
	rootCmd.Flags().BoolVarP(&verbose, "verbose", "v", false, "Enable verbose output")
	rootCmd.Flags().BoolVar(&webMode, "web", false, "Start web dashboard mode")
	rootCmd.Flags().StringVar(&webPort, "port", ":9090", "Web dashboard port")

	// Version command
	versionCmd := &cobra.Command{
		Use:   "version",
		Short: "Print version information",
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Printf("FluxFuzzer version %s\n", version)
		},
	}
	rootCmd.AddCommand(versionCmd)

	// Web command (dedicated)
	webCmd := &cobra.Command{
		Use:   "web",
		Short: "Start web dashboard",
		Run:   runWebDashboard,
	}
	webCmd.Flags().StringVarP(&webPort, "port", "p", ":9090", "Web dashboard port")
	rootCmd.AddCommand(webCmd)

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func printBanner() {
	fmt.Println()
	fmt.Println("  ╔═══════════════════════════════════════════════════════════╗")
	fmt.Println("  ║   ███████╗██╗     ██╗   ██╗██╗  ██╗    FluxFuzzer         ║")
	fmt.Println("  ║   ██╔════╝██║     ██║   ██║╚██╗██╔╝    Smart Stateful     ║")
	fmt.Println("  ║   █████╗  ██║     ██║   ██║ ╚███╔╝     Web Fuzzer         ║")
	fmt.Println("  ║   ██╔══╝  ██║     ██║   ██║ ██╔██╗                        ║")
	fmt.Println("  ║   ██║     ███████╗╚██████╔╝██╔╝ ██╗    v" + version + "          ║")
	fmt.Println("  ║   ╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝                       ║")
	fmt.Println("  ╚═══════════════════════════════════════════════════════════╝")
	fmt.Println()
}

func runFuzzer(cmd *cobra.Command, args []string) {
	printBanner()

	// If web mode is enabled, start web dashboard
	if webMode {
		runWebDashboard(cmd, args)
		return
	}

	// Validate required flags
	if targetURL == "" && configFile == "" {
		fmt.Println("  [!] No target specified. Use --url or --config")
		fmt.Println()
		fmt.Println("  Quick start:")
		fmt.Println("    fluxfuzzer -u http://target.com/FUZZ -w wordlists/common.txt")
		fmt.Println()
		fmt.Println("  Or start web dashboard:")
		fmt.Println("    fluxfuzzer web")
		fmt.Println()
		return
	}

	if verbose {
		fmt.Printf("  [*] Target: %s\n", targetURL)
		fmt.Printf("  [*] Threads: %d\n", threads)
		fmt.Printf("  [*] Rate: %d RPS\n", rps)
		fmt.Printf("  [*] Timeout: %ds\n", timeout)
	}

	// Setup signal handling for graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Initialize fuzzing engine
	fmt.Println("  [*] Initializing scanning engine...")

	detector := owasp.NewDetector(nil)

	fmt.Printf("  [*] Scanning target: %s\n", targetURL)

	// Parse URL to extract parameters
	u, err := url.Parse(targetURL)
	if err != nil {
		fmt.Printf("  [!] Invalid URL: %v\n", err)
		return
	}

	params := make(map[string]string)
	query := u.Query()
	for k, v := range query {
		if len(v) > 0 {
			params[k] = v[0]
		}
	}

	// Also add some default params for testing if none exist
	if len(params) == 0 {
		params["id"] = "1"
		params["search"] = "test"
	}

	target := &owasp.Target{
		URL:        targetURL,
		Method:     "GET",
		Parameters: params,
	}

	// Create context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Second)
	defer cancel()

	// Run scan in goroutine to allow cancellation
	done := make(chan struct{})

	go func() {
		findings, err := detector.Scan(ctx, target)
		if err != nil {
			fmt.Printf("\n  [!] Scan error: %v\n", err)
		} else {
			fmt.Printf("\n  [*] Scan complete. Found %d issues.\n", len(findings))
			for _, f := range findings {
				fmt.Printf("  [+] [%s] %s: %s\n", f.Severity, f.Type, f.Description)
				if f.Payload != "" {
					fmt.Printf("      Payload: %s\n", f.Payload)
				}
			}
		}
		close(done)
	}()

	// Wait for completion or signal
	select {
	case <-done:
		// Completed
	case <-sigChan:
		fmt.Println("\n  [*] Shutting down gracefully...")
		cancel()
	}
}

func runWebDashboard(cmd *cobra.Command, args []string) {
	printBanner()

	fmt.Println("  [*] Starting Web Dashboard...")
	fmt.Println()
	fmt.Printf("  🌐 Open your browser at: http://localhost%s\n", webPort)
	fmt.Println()
	fmt.Println("  Press Ctrl+C to stop")
	fmt.Println()

	// Setup signal handling
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Start web server
	server := web.NewServer()

	go func() {
		if err := server.Start(webPort); err != nil {
			fmt.Printf("  [!] Server error: %v\n", err)
			os.Exit(1)
		}
	}()

	// Wait for signal
	<-sigChan
	fmt.Println("\n  [*] Shutting down web server...")
	server.Stop()
}
