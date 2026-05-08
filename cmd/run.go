package cmd

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	"github.com/hxri-nxrxyxn/rt/internal/engine"
	"github.com/spf13/cobra"
)

var runCmd = &cobra.Command{
	Use:   "run [model_path]",
	Short: "Run a model interactively",
	Args:  cobra.MaximumNArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		if len(args) == 0 {
			fmt.Println("Please specify a model path. (e.g. rt run ./models/model.litertlm)")
			return
		}
		modelPath := args[0]
		backend, _ := cmd.Flags().GetString("backend")
		promptFlag, _ := cmd.Flags().GetString("prompt")
		
		e := engine.NewEngine(modelPath, backend)

		if promptFlag != "" {
			ch, err := e.Stream(promptFlag)
			if err != nil {
				fmt.Printf("Error: %v\n", err)
				os.Exit(1)
			}
			for token := range ch {
				fmt.Print(token)
			}
			fmt.Println()
			return
		}

		fmt.Printf("Loading model %s on %s...\n", modelPath, backend)

		reader := bufio.NewReader(os.Stdin)
		fmt.Println("Chat started! Type 'exit' or 'quit' to stop.")

		for {
			fmt.Print("User: ")
			prompt, err := reader.ReadString('\n')
			if err != nil {
				break
			}
			prompt = strings.TrimSpace(prompt)
			if prompt == "exit" || prompt == "quit" {
				break
			}
			if prompt == "" {
				continue
			}

			fmt.Print("Assistant: ")
			ch, err := e.Stream(prompt)
			if err != nil {
				fmt.Printf("\nError: %v\n", err)
				continue
			}

			for token := range ch {
				fmt.Print(token)
			}
			fmt.Println()
		}
	},
}

func init() {
	runCmd.Flags().StringP("backend", "b", "cpu", "Backend to use (cpu/gpu)")
	runCmd.Flags().StringP("prompt", "p", "", "Single prompt to run")
	rootCmd.AddCommand(runCmd)
}
