# Parent Class
import os
from pathlib import Path

from backend.src.memory.utils import MODEL, CHAT_NAME
from backend.src.memory.utils import read_skill
from backend.src.memory.logger_utils import logger
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.contents import ChatHistory


class BaseAgent:
    def __init__(self, name: str, description: str, usage_prompt: str,
                 prompt_folder: str):
        # load skill instruction from given path and initialize
        self.name = name
        self.description = description
        self.model = MODEL
        self.usage_prompt = usage_prompt  # for assign question to agent
        self.system_prompt = ""  # for add chat system prompt

        # Get the directory of the current running script
        current_dir = str(Path(__file__).parent.resolve()) + os.sep
        if prompt_folder is not None:
            skill_dir = read_skill(current_dir+prompt_folder+os.sep+"SKILL.md")
            self.skill_instructions = skill_dir["skill_instructions"]
            logger.info(f"🧬 [{self.name}] skill loaded successfully via Ollama.")  # \n [{self.skill_instructions}] ")
        else:
            logger.info(f"🧬 [{self.name}] skill no file specify")
        self.init_system_prompt()
        # logger.debug(f"🧬 [{self.name}] chat system prompt initialized successfully[{self.system_prompt}]")

    def init_system_prompt(self):
        # to be overwrite
        return

    def init_chat(self, chat_history: ChatHistory):
        # Create chat history structure (replaces the messages=[...] dict)
        logger.debug(f"🧬 Initialize [{self.name}] chat, with prompt {self.system_prompt}")
        chat_history.add_system_message(self.system_prompt)

    # def add_user_message(self, user_query: str):
    #     # Create chat history structure (replaces the messages=[...] dict)
    #     self.chat_history.add_user_message(user_query)