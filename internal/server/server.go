package server

import (
	"fmt"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/hxri-nxrxyxn/rt/internal/engine"
)

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatCompletionRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
	Stream   bool      `json:"stream"`
}

type ChatCompletionResponse struct {
	ID      string `json:"id"`
	Object  string `json:"object"`
	Created int64  `json:"created"`
	Model   string `json:"model"`
	Choices []struct {
		Index   int `json:"index"`
		Message struct {
			Role    string `json:"role"`
			Content string `json:"content"`
		} `json:"message"`
		FinishReason string `json:"finish_reason"`
	} `json:"choices"`
}

func Start(port int) error {
	r := gin.Default()

	r.POST("/v1/chat/completions", func(c *gin.Context) {
		var req ChatCompletionRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		modelPath := req.Model
		e := engine.NewEngine(modelPath, "cpu")

		if req.Stream {
			c.Header("Content-Type", "text/event-stream")
			c.Header("Cache-Control", "no-cache")
			c.Header("Connection", "keep-alive")

			lastMsg := req.Messages[len(req.Messages)-1].Content
			ch, err := e.Stream(lastMsg)
			if err != nil {
				c.SSEvent("error", err.Error())
				return
			}

			c.Stream(func(w io.Writer) bool {
				for token := range ch {
					c.SSEvent("message", gin.H{
						"choices": []gin.H{
							{
								"delta": gin.H{"content": token},
							},
						},
					})
				}
				c.SSEvent("message", "[DONE]")
				return false
			})
		} else {
			lastMsg := req.Messages[len(req.Messages)-1].Content
			ch, err := e.Stream(lastMsg)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
				return
			}

			var fullText string
			for token := range ch {
				fullText += token
			}

			resp := ChatCompletionResponse{
				ID:      "chatcmpl-rt",
				Object:  "chat.completion",
				Created: 123456789,
				Model:   req.Model,
			}
			choice := struct {
				Index   int `json:"index"`
				Message struct {
					Role    string `json:"role"`
					Content string `json:"content"`
				} `json:"message"`
				FinishReason string `json:"finish_reason"`
			}{
				Index: 0,
				Message: struct {
					Role    string `json:"role"`
					Content string `json:"content"`
				}{
					Role:    "assistant",
					Content: fullText,
				},
				FinishReason: "stop",
			}
			resp.Choices = append(resp.Choices, choice)

			c.JSON(http.StatusOK, resp)
		}
	})

	return r.Run(fmt.Sprintf(":%d", port))
}
