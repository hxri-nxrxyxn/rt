import typer
from pathlib import Path
from typing import Optional
import os
from huggingface_hub import hf_hub_download, list_repo_files
import litert_lm

app = typer.Typer(help="LiteRT-LM Wrapper for easy model management and serving.")

MODELS_DIR = Path("models")

def get_models_dir():
    MODELS_DIR.mkdir(exist_ok=True)
    return MODELS_DIR

def find_model_path(model_name: str) -> Path:
    target_dir = get_models_dir()
    # Try exact match first
    path = target_dir / model_name
    if path.exists():
        return path
    
    # Try adding .litertlm extension
    path = target_dir / f"{model_name}.litertlm"
    if path.exists():
        return path
    
    # Try fuzzy match (prefix)
    matches = list(target_dir.glob(f"{model_name}*.litertlm"))
    if matches:
        return matches[0]
    
    raise FileNotFoundError(f"Model {model_name} not found in {target_dir}")

@app.command()
def pull(model_id: str, filename: Optional[str] = None):
    """Download a model from Hugging Face."""
    target_dir = get_models_dir()
    
    if not filename:
        typer.echo(f"Searching for .litertlm files in {model_id}...")
        files = list_repo_files(model_id)
        litert_files = [f for f in files if f.endswith(".litertlm")]
        
        if not litert_files:
            typer.echo(f"Error: No .litertlm files found in repository {model_id}")
            raise typer.Exit(code=1)
        
        if len(litert_files) > 1:
            typer.echo("Multiple .litertlm files found. Please specify one using --filename:")
            for f in litert_files:
                typer.echo(f"  - {f}")
            raise typer.Exit(code=1)
        
        filename = litert_files[0]

    typer.echo(f"Downloading {filename} from {model_id}...")
    
    # Download directly to the models directory
    path = hf_hub_download(
        repo_id=model_id,
        filename=filename,
        local_dir=target_dir,
        local_dir_use_symlinks=False
    )
    
    typer.echo(f"Successfully downloaded to: {path}")

@app.command(name="list")
def list_models_cmd():
    """List downloaded models."""
    target_dir = get_models_dir()
    models = sorted(list(target_dir.glob("*.litertlm")))
    
    if not models:
        typer.echo("No models found in ./models")
        return

    typer.echo("Downloaded models:")
    for m in models:
        size_mb = m.stat().st_size / (1024 * 1024)
        typer.echo(f"  - {m.name} ({size_mb:.1f} MB)")

@app.command()
def tui():
    """Start the TUI (Terminal User Interface) for chatting with models."""
    from .tui import run_tui
    run_tui()

@app.command()
def run(model_name: Optional[str] = None, gpu: bool = True):
    """Run an interactive chat with a model. If no model is specified, starts TUI."""
    if model_name is None:
        from .tui import run_tui
        run_tui()
        return

    try:
        model_path = find_model_path(model_name)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(code=1)

    typer.echo(f"Loading model: {model_path}...")
    backend = litert_lm.Backend.GPU if gpu else litert_lm.Backend.CPU
    
    from .server import load_tools
    tools = load_tools()

    try:
        # Note: litert_lm.Engine and conversation should be used in a with block for safety
        with litert_lm.Engine(str(model_path), backend=backend) as engine:
            with engine.create_conversation(tools=tools) as conversation:
                typer.echo("Chat started! Type 'exit' or 'quit' to stop.")
                while True:
                    user_input = typer.prompt("User")
                    if user_input.lower() in ["exit", "quit"]:
                        break
                    
                    print("Assistant: ", end="", flush=True)
                    for chunk in conversation.send_message_async(user_input):
                        if chunk["content"]:
                            text = chunk["content"][0].get("text", "")
                            print(text, end="", flush=True)
                    print() # Newline after response
    except Exception as e:
        typer.echo(f"Error during inference: {e}")
        raise typer.Exit(code=1)

@app.command()
def serve(port: int = 8000):
    """Start the OpenAI-compatible server."""
    from .server import run_server
    typer.echo(f"Starting server on port {port}...")
    run_server(port)

if __name__ == "__main__":
    app()
