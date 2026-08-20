#!/usr/bin/env python
import asyncio

import uvicorn

from backend.src.cores.factory import kernel_instance, orchestrator_instance


def run_app():
    """Run backend api server."""
    uvicorn.run("backend.src.cores.apis:app", host="127.0.0.1", port=8000, reload=True)


def start_chat_session():
    """Start a chat session in terminal."""
    # Call asyncio.run EXACTLY ONCE here to kick off the whole experience
    asyncio.run(start_chat_session(kernel_instance, orchestrator_instance))


if __name__ == "__main__":
    run_app()
