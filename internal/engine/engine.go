package engine

import (
	"bufio"
	"fmt"
	"io"
	"os/exec"
)

type Engine struct {
	ModelPath string
	Backend   string
}

func NewEngine(modelPath string, backend string) *Engine {
	if backend == "" {
		backend = "cpu"
	}
	return &Engine{
		ModelPath: modelPath,
		Backend:   backend,
	}
}

func (e *Engine) Generate(prompt string, out io.Writer) error {
	cmd := exec.Command("litert-lm", "run", e.ModelPath, "--prompt", prompt, "--backend", e.Backend)
	
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}

	if err := cmd.Start(); err != nil {
		return err
	}

	scanner := bufio.NewScanner(stdout)
	for scanner.Scan() {
		fmt.Fprintln(out, scanner.Text())
	}

	return cmd.Wait()
}

// Stream sends the prompt and returns a channel of strings (tokens/lines)
func (e *Engine) Stream(prompt string) (chan string, error) {
	ch := make(chan string)
	
	cmd := exec.Command("litert-lm", "run", e.ModelPath, "--prompt", prompt, "--backend", e.Backend)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}

	if err := cmd.Start(); err != nil {
		return nil, err
	}

	go func() {
		defer close(ch)
		// We read word by word or chunk by chunk
		// Scanner with split by words?
		reader := bufio.NewReader(stdout)
		for {
			line, err := reader.ReadString('\n')
			if line != "" {
				ch <- line
			}
			if err != nil {
				break
			}
		}
		cmd.Wait()
	}()

	return ch, nil
}
