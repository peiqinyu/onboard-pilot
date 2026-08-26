from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import KernelArguments
from fastapi.middleware.cors import CORSMiddleware
from backend.src.memory.logger_utils import logger
from backend.src.memory.utils import construct_user_prompt
from backend.src.cores.factory import kernel_instance, orchestrator_instance, \
    linear_plugin, rag_plugin, chat_client, settings

# Setup FastAPI
app = FastAPI()
# Allow your React local dev server to talk to the Python API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, swap "*" for your explicit frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Global session store to keep track of chat history per user
# In production, use Redis or a database
sessions = {}


# Pydantic schema for incoming requests
class ChatRequest(BaseModel):
    session_id: str
    user_input: str


@app.post("/api/chat")
async def chat_endpoint(chat_request: ChatRequest):
    user_input = chat_request.user_input.strip()
    session_id = chat_request.session_id
    if not user_input:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

        # Route agent dynamically
    agent, explanation = orchestrator_instance.assign_agent(user_input)
    if agent is None:
        return {"response": "I can answer technical related questions only, please ask another question!",
                "agent_assigned": None}

    # Initialize or fetch the specific user session history
    if session_id not in sessions:
        sessions[session_id] = {
            "current_agent_name": None,
            "history": ChatHistory()
        }

    session_data = sessions[session_id]
    # Handle agent re-assignment and history wipe conditions
    if session_data["current_agent_name"] is None or agent.name != session_data["current_agent_name"]:
        session_data["current_agent_name"] = agent.name
        session_data["history"] = ChatHistory()
        session_data["history"].add_system_message(agent.system_prompt)
        logger.debug(f"🤖 (Re)Assign task to agent {agent.name}")

    # Run Research RAG/Linear logic if applicable
    if session_data["current_agent_name"] == orchestrator_instance.agent_dir["Research"].name:
        filtered_user_input = orchestrator_instance.filter_words(user_input)

        # Invoke your RAG/Linear semantic kernel plugins
        rag_result = await kernel_instance.invoke(function=rag_plugin["search_k_content"],
                                                  arguments=KernelArguments(query=filtered_user_input))
        linear_result = await kernel_instance.invoke(function=linear_plugin["search_k_content"],
                                                     arguments=KernelArguments(query=filtered_user_input))

        refined_user_input = construct_user_prompt(str(rag_result), str(linear_result), user_input)
    else:
        refined_user_input = user_input

    # Add query to history
    session_data["history"].add_user_message(refined_user_input)

    try:
        # Await LLM completion
        response = await chat_client.get_chat_message_contents(
            chat_history=session_data["history"],
            settings=settings
        )

        ai_text = "".join([chat_msg.inner_content.message.content for chat_msg in response])

        # Keep track of response inside chat history
        session_data["history"].add_assistant_message(ai_text)

        return {"response": ai_text,
                "agent_assigned": agent.name}

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
