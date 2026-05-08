from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Input, Static, RichLog
from textual.containers import Container, Vertical, ScrollableContainer
from textual.screen import Screen
from pathlib import Path
import litert_lm
import threading
import queue
import time
import re

class ModelListItem(ListItem):
    def __init__(self, model_path: Path):
        super().__init__(Label(model_path.name))
        self.model_path = model_path

class ModelSelector(Screen):
    def __init__(self, models):
        super().__init__()
        self.models = models

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Select a model to start chatting:", id="selector_label")
        yield ListView(*[ModelListItem(m) for m in self.models], id="model_list")
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected):
        self.app.start_chat(event.item.model_path)

class ChatScreen(Screen):
    BINDINGS = [("t", "toggle_thinking", "Toggle Thinking Mode")]

    def __init__(self, model_path):
        super().__init__()
        self.model_path = model_path
        self.engine = None
        self.conversation = None
        self.msg_queue = queue.Queue()
        self.current_thought = ""
        self.current_text = ""
        self.backend_name = "Detecting..."
        self.in_thought_channel = False
        self.thinking_enabled = True
        self.is_busy = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="chat_container"):
            yield RichLog(id="chat_log", highlight=True, markup=True, wrap=True)
            yield Static("", id="active_response")
        yield Label("Loading performance metrics...", id="perf_label")
        yield Input(placeholder="Type your message here...", id="chat_input")
        yield Footer()

    def on_mount(self):
        self.query_one("#chat_log").write(f"[bold blue]System:[/bold blue] Loading {self.model_path.name}...")
        self.query_one("#chat_input").disabled = True
        threading.Thread(target=self.load_engine, daemon=True).start()
        self.set_interval(0.05, self.check_queue)

    def action_toggle_thinking(self):
        self.thinking_enabled = not self.thinking_enabled
        status = "ENABLED" if self.thinking_enabled else "DISABLED"
        color = "green" if self.thinking_enabled else "red"
        self.query_one("#chat_log").write(f"[bold magenta]System:[/bold magenta] Thinking mode [{color}]{status}[/{color}]")
        self.update_perf_label()

    def update_perf_label(self, perf_metrics="N/A"):
        thinking_status = "Thinking: ON" if self.thinking_enabled else "Thinking: OFF"
        busy_status = " [busy]" if self.is_busy else ""
        self.query_one("#perf_label").update(
            f"Model: {self.model_path.name} | Backend: {self.backend_name} | {thinking_status} | {perf_metrics}{busy_status}"
        )

    def load_engine(self):
        try:
            import subprocess
            backend = litert_lm.Backend.CPU
            self.backend_name = "CPU"
            try:
                subprocess.check_output(["nvidia-smi"], stderr=subprocess.STDOUT)
                backend = litert_lm.Backend.GPU
                self.backend_name = "GPU"
            except:
                pass
            
            self.engine = litert_lm.Engine(str(self.model_path), backend=backend)
            self.conversation = self.engine.create_conversation()
            self.msg_queue.put(("system", f"Model loaded on {self.backend_name}! Press 'T' to toggle thinking mode."))
            self.msg_queue.put(("perf_init", ""))
            self.msg_queue.put(("ready", ""))
        except Exception as e:
            self.msg_queue.put(("error", f"Failed to load model: {e}"))

    def check_queue(self):
        while not self.msg_queue.empty():
            msg_type, content = self.msg_queue.get()
            log = self.query_one("#chat_log")
            active = self.query_one("#active_response")
            chat_input = self.query_one("#chat_input")
            
            if msg_type == "system":
                log.write(f"[bold blue]System:[/bold blue] {content}")
            elif msg_type == "error":
                log.write(f"[bold red]Error:[/bold red] {content}")
                self.is_busy = False
                chat_input.disabled = False
                chat_input.focus()
            elif msg_type == "perf_init":
                self.update_perf_label()
            elif msg_type == "ready":
                chat_input.disabled = False
                chat_input.focus()
            elif msg_type == "thought_chunk":
                if self.thinking_enabled: # Only show if enabled
                    self.current_thought += content
                    self.update_active_display(active)
            elif msg_type == "text_chunk":
                self.current_text += content
                self.update_active_display(active)
            elif msg_type == "perf":
                self.update_perf_label(content)
            elif msg_type == "assistant_done":
                display_text = ""
                if self.current_thought and self.thinking_enabled:
                    display_text += f"[italic cyan]Thought:[/italic cyan]\n[dim cyan]{self.current_thought}[/dim cyan]\n\n"
                display_text += self.current_text
                log.write(f"[bold green]Assistant:[/bold green] {display_text}")
                active.update("")
                self.current_thought = ""
                self.current_text = ""
                self.in_thought_channel = False
                self.is_busy = False
                chat_input.disabled = False
                chat_input.focus()
                self.update_perf_label(content)

    def update_active_display(self, active_widget):
        display = "[bold green]Assistant:[/bold green] "
        if self.current_thought and self.thinking_enabled:
            display += f"[italic cyan]Thinking...[/italic cyan]\n[dim cyan]{self.current_thought}[/dim cyan]\n"
        if self.current_text:
            display += f"\n{self.current_text}"
        active_widget.update(display)

    async def on_input_submitted(self, event: Input.Submitted):
        if self.is_busy: return
        user_text = event.value.strip()
        if not user_text: return
        if user_text.lower() in ["exit", "quit"]:
            self.app.pop_screen()
            return

        chat_input = self.query_one("#chat_input")
        chat_input.value = ""
        chat_input.disabled = True
        self.is_busy = True
        self.update_perf_label("Inference...")
        
        log = self.query_one("#chat_log")
        log.write(f"[bold yellow]User:[/bold yellow] {user_text}")

        if not self.conversation:
            log.write("[bold red]System:[/bold red] Engine not ready yet.")
            self.is_busy = False
            chat_input.disabled = False
            return

        # Prepend thinking trigger if enabled, otherwise explicitly tell it NOT to think
        if self.thinking_enabled:
            prompt = f"<|think|> {user_text}"
        else:
            prompt = f"Answer the following directly without using a reasoning channel or thinking process: {user_text}"
            
        threading.Thread(target=self.run_inference, args=(prompt,), daemon=True).start()

    def run_inference(self, text):
        try:
            start_time = time.time()
            first_token_time = None
            token_count = 0
            self.in_thought_channel = False
            
            for chunk in self.conversation.send_message_async(text):
                if not first_token_time:
                    first_token_time = time.time()
                
                for item in chunk.get("content", []):
                    item_text = item.get("text", "")
                    
                    if "<|channel>thought" in item_text:
                        self.in_thought_channel = True
                        item_text = item_text.replace("<|channel>thought", "")
                    
                    if "<channel|>" in item_text:
                        self.in_thought_channel = False
                        parts = item_text.split("<channel|>", 1)
                        if parts[0]: self.msg_queue.put(("thought_chunk", parts[0]))
                        if parts[1]: self.msg_queue.put(("text_chunk", parts[1]))
                        continue

                    if self.in_thought_channel:
                        self.msg_queue.put(("thought_chunk", item_text))
                    else:
                        self.msg_queue.put(("text_chunk", item_text))
                        token_count += len(item_text.split()) + 1
            
            end_time = time.time()
            total_time = end_time - start_time
            ttft = (first_token_time - start_time) * 1000 if first_token_time else 0
            tps = token_count / total_time if total_time > 0 else 0
            self.msg_queue.put(("perf", f"TTFT: {ttft:.0f}ms | Speed: {tps:.1f} tokens/sec"))
            self.msg_queue.put(("assistant_done", ""))
        except Exception as e:
            self.msg_queue.put(("error", f"Inference error: {e}"))

class LitertTUI(App):
    CSS = """
    #selector_label { padding: 1 2; background: $primary; color: white; text-align: center; width: 100%; }
    #model_list { margin: 1 2; border: solid $accent; }
    #chat_container { height: 1fr; margin: 1 2; }
    #chat_log { height: 1fr; border: tall $primary; background: $surface; }
    #active_response { padding: 0 1; height: auto; max-height: 25; background: $surface; color: $text; }
    #perf_label { margin: 0 2; color: $text-muted; text-style: italic; }
    #chat_input { margin: 0 2 1 2; }
    #chat_input:disabled { opacity: 0.5; }
    """
    def on_mount(self):
        from .cli import get_models_dir
        target_dir = get_models_dir()
        models = sorted(list(target_dir.glob("*.litertlm")))
        if not models: self.exit("No models found.")
        else: self.push_screen(ModelSelector(models))
    def start_chat(self, model_path: Path):
        self.push_screen(ChatScreen(model_path))

def run_tui():
    LitertTUI().run()
