package tui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textarea"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/hxri-nxrxyxn/rt/internal/engine"
)

type errMsg error

type model struct {
	viewport    viewport.Model
	textarea    textarea.Model
	messages    []string
	engine      *engine.Engine
	err         error
	isStreaming bool
	streamCh    chan string
}

func initialModel(e *engine.Engine) model {
	ta := textarea.New()
	ta.Placeholder = "Send a message..."
	ta.Focus()
	ta.Prompt = "> "
	ta.SetWidth(80)
	ta.SetHeight(3)
	ta.ShowLineNumbers = false

	vp := viewport.New(80, 15)
	vp.SetContent(`RT / CHAT`)

	return model{
		textarea: ta,
		viewport: vp,
		messages: []string{},
		engine:   e,
	}
}

func (m model) Init() tea.Cmd {
	return textarea.Blink
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var (
		tiCmd tea.Cmd
		vpCmd tea.Cmd
	)

	m.textarea, tiCmd = m.textarea.Update(msg)
	m.viewport, vpCmd = m.viewport.Update(msg)

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.viewport.Width = msg.Width
		m.viewport.Height = msg.Height - 6
		m.textarea.SetWidth(msg.Width)
		return m, nil

	case tea.KeyMsg:
		switch msg.Type {
		case tea.KeyCtrlC, tea.KeyEsc:
			return m, tea.Quit
		case tea.KeyEnter:
			if m.isStreaming {
				return m, nil
			}
			prompt := m.textarea.Value()
			if strings.TrimSpace(prompt) == "" {
				return m, nil
			}
			m.messages = append(m.messages, fmt.Sprintf("[USER] %s", prompt))
			m.textarea.Reset()
			m.isStreaming = true
			m.messages = append(m.messages, "[ASSISTANT] ")
			m.viewport.SetContent(strings.Join(m.messages, "\n"))
			m.viewport.GotoBottom()

			ch, err := m.engine.Stream(prompt)
			if err != nil {
				m.err = err
				m.isStreaming = false
				return m, nil
			}
			m.streamCh = ch
			return m, waitForToken(m.streamCh)
		}

	case tokenMsg:
		m.messages[len(m.messages)-1] += string(msg)
		m.viewport.SetContent(strings.Join(m.messages, "\n"))
		m.viewport.GotoBottom()
		return m, waitForToken(m.streamCh)

	case doneMsg:
		m.isStreaming = false
		m.messages = append(m.messages, "") // Spacer
		m.viewport.SetContent(strings.Join(m.messages, "\n"))
		m.viewport.GotoBottom()
		return m, nil
	}

	return m, tea.Batch(tiCmd, vpCmd)
}

func (m model) View() string {
	if m.err != nil {
		return fmt.Sprintf("Error: %v", m.err)
	}
	return fmt.Sprintf(
		"%s\n\n%s",
		m.viewport.View(),
		m.textarea.View(),
	)
}

type tokenMsg string
type doneMsg struct{}

func waitForToken(ch chan string) tea.Cmd {
	return func() tea.Msg {
		token, ok := <-ch
		if !ok {
			return doneMsg{}
		}
		return tokenMsg(token)
	}
}

func Run(e *engine.Engine) error {
	m := initialModel(e)
	p := tea.NewProgram(m, tea.WithAltScreen())
	_, err := p.Run()
	return err
}
