package cmd

import (
	"fmt"

	"github.com/hxri-nxrxyxn/rt/internal/server"
	"github.com/spf13/cobra"
)

var serveCmd = &cobra.Command{
	Use:   "serve",
	Short: "Start the OpenAI-compatible server",
	Run: func(cmd *cobra.Command, args []string) {
		port, _ := cmd.Flags().GetInt("port")
		fmt.Printf("Starting server on port %d...\n", port)
		if err := server.Start(port); err != nil {
			fmt.Printf("Error starting server: %v\n", err)
		}
	},
}

func init() {
	serveCmd.Flags().IntP("port", "p", 8000, "Port to listen on")
	rootCmd.AddCommand(serveCmd)
}
