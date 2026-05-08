package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "rt",
	Short: "RT is a CLI wrapper for LiteRT-LM models",
	Long:  `A fast and efficient CLI wrapper for running and serving LiteRT-LM models with OpenAI compatibility and TUI support.`,
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	// Global flags can be added here
}
