package cmd

import (
	"fmt"
	"os"

	"github.com/hxri-nxrxyxn/rt/internal/models"
	"github.com/spf13/cobra"
)

var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List downloaded models",
	Run: func(cmd *cobra.Command, args []string) {
		list, err := models.List()
		if err != nil {
			fmt.Printf("Error listing models: %v\n", err)
			return
		}

		if len(list) == 0 {
			fmt.Println("No models found in ./models")
			return
		}

		fmt.Println("Downloaded models:")
		for _, m := range list {
			fmt.Printf("  - %s (%.1f MB)\n", m.Name, float64(m.Size)/(1024*1024))
		}
	},
}

var pullCmd = &cobra.Command{
	Use:   "pull [repo_id] [filename]",
	Short: "Download a model from Hugging Face",
	Args:  cobra.ExactArgs(2),
	Run: func(cmd *cobra.Command, args []string) {
		repoID := args[0]
		filename := args[1]
		err := models.Pull(repoID, filename)
		if err != nil {
			fmt.Printf("Error pulling model: %v\n", err)
			os.Exit(1)
		}
	},
}

func init() {
	rootCmd.AddCommand(listCmd)
	rootCmd.AddCommand(pullCmd)
}
