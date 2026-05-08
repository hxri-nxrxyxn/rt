package cmd

import (
	"fmt"
	"os"

	"github.com/hxri-nxrxyxn/rt/internal/engine"
	"github.com/hxri-nxrxyxn/rt/internal/tui"
	"github.com/spf13/cobra"
)

var tuiCmd = &cobra.Command{
	Use:   "tui [model_path]",
	Short: "Start the TUI chat interface",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		modelPath := args[0]
		backend, _ := cmd.Flags().GetString("backend")
		
		e := engine.NewEngine(modelPath, backend)
		if err := tui.Run(e); err != nil {
			fmt.Printf("Error starting TUI: %v\n", err)
			os.Exit(1)
		}
	},
}

func init() {
	tuiCmd.Flags().StringP("backend", "b", "cpu", "Backend to use (cpu/gpu)")
	rootCmd.AddCommand(tuiCmd)
}
