#!/usr/bin/env python
import asyncio
import json
import uvicorn

from backend.src.cores.factory import kernel_instance, orchestrator_instance, start_chat_session, answer_questions


def run_app():
    """Run backend api server."""
    uvicorn.run("backend.src.cores.apis:app", host="127.0.0.1", port=8000, reload=True)


def start_chat():
    """Start a chat session in terminal."""
    # Call asyncio.run EXACTLY ONCE here to kick off the whole experience
    asyncio.run(start_chat_session(kernel_instance, orchestrator_instance))


def get_chat_responses(questions: list[str]) -> list[tuple]:
    """Get a chat response for testing."""
    # Call asyncio.run EXACTLY ONCE here to kick off the whole experience
    responses = asyncio.run(answer_questions(kernel_instance,
                                             orchestrator_instance, questions, 'Research'))
    # format_responses = []
    # for res_str in responses:
    #     # res_json = json.loads(res_str)
    #     format_responses.append(res_json)
    #     print(res_json)

    return responses


if __name__ == "__main__":
    # run_app()
    question_list = [
        "what is the deployment process?",
                     "what is the testing process?",
                     "what is this repo about https://github.com/openai/openai-cookbook?"
    ]
    res_list = get_chat_responses(question_list)
    # print(res)
