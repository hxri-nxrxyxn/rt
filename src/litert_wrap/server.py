from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
import json
import asyncio
import litert_lm
from pathlib import Path
import logging
import importlib.util
import inspect
import anyio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LiteRT-LM OpenAI Wrapper")

class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: Optional[bool] = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = "auto"

# Global engine storage
engines = {}

def detect_backend():
    import subprocess
    try:
        subprocess.check_output(["nvidia-smi"], stderr=subprocess.STDOUT)
        return litert_lm.Backend.GPU
    except:
        return litert_lm.Backend.CPU

def get_engine(model_path: Path):
    path_str = str(model_path)
    if path_str not in engines:
        backend = detect_backend()
        logger.info(f"Loading engine for {path_str} using {backend}")
        engines[path_str] = litert_lm.Engine(path_str, backend=backend)
    return engines[path_str]

def create_dummy_tool(tool_def: Dict[str, Any]):
    """Creates a dummy Python function from an OpenAI tool definition."""
    name = tool_def["function"]["name"]
    description = tool_def["function"]["description"]
    
    # We create a function that just returns its arguments as a JSON string
    # This allows us to detect that a tool was "called"
    def dummy_fn(**kwargs):
        return json.dumps({"__tool_call__": name, "args": kwargs})
    
    dummy_fn.__name__ = name
    dummy_fn.__doc__ = description
    # Note: LiteRT-LM uses the docstring and signature for schema generation.
    # For n8n tools, we don't have the Python signature easily, 
    # but we can try to use the description.
    return dummy_fn

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    from .cli import find_model_path
    try:
        model_path = find_model_path(request.model)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Model {request.model} not found")

    engine = get_engine(model_path)
    
    # Convert tools from request if present
    runtime_tools = []
    if request.tools:
        for t in request.tools:
            runtime_tools.append(create_dummy_tool(t))
    
    # Convert messages to litert_lm format
    formatted_messages = []
    for msg in request.messages:
        role = msg.role
        if role == "tool":
            role = "tool" # LiteRT-LM handles tool role
        
        content = msg.content or ""
        formatted_messages.append({
            "role": role,
            "content": [{"type": "text", "text": content}]
        })

    # Note: For n8n tool calling, we usually don't want streaming 
    # because n8n needs the full tool_calls JSON at once.
    
    def run_inference():
        with engine.create_conversation(messages=formatted_messages[:-1], tools=runtime_tools) as conversation:
            last_msg = formatted_messages[-1]["content"][0]["text"]
            full_response = ""
            
            # The LiteRT-LM Python API handles the tool execution loop.
            # If we used dummy functions, it will call them, get the JSON, 
            # and send it back to the model. This is NOT what we want for n8n.
            
            # TODO: We need a way to stop LiteRT-LM from auto-executing 
            # OR we need to detect the tool call tokens manually.
            
            # For now, let's try to detect if the model outputted a tool call 
            # based on the known LiteRT-LM tool call format.
            for chunk in conversation.send_message_async(last_msg):
                if chunk["content"]:
                    text = chunk["content"][0].get("text", "")
                    full_response += text
            
            return full_response

    response_text = await anyio.to_thread.run_sync(run_inference)
    
    # Check if the response contains a tool call in LiteRT-LM format
    # Format is usually: <|tool_call|>call:name{args}<tool_call|>
    if "<|tool_call|>" in response_text:
        # Parse the tool call
        import re
        match = re.search(r"<\|tool_call\|>call:(\w+)\{(.*?)\}<tool_call\|>", response_text)
        if match:
            tool_name = match.group(1)
            try:
                # The arguments are sometimes in a custom format, but often JSON-like
                args_str = "{" + match.group(2) + "}"
                # Clean up if it's not perfect JSON (e.g. key:val instead of "key":"val")
                # This is a bit hacky, but gemma-4 outputs specific syntax
                # For n8n, we want standard JSON
                args = {} # Simplification for now
                
                return {
                    "id": "chatcmpl-litert",
                    "object": "chat.completion",
                    "created": 123456789,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": match.group(2) # Return raw args for n8n to parse
                                }
                            }]
                        },
                        "finish_reason": "tool_calls"
                    }]
                }
            except:
                pass

    return {
        "id": "chatcmpl-litert",
        "object": "chat.completion",
        "created": 123456789,
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": response_text},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }

async def stream_generator(engine, messages, model_name, tools):
    # (Existing streaming logic...)
    pass

def run_server(port: int):
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
