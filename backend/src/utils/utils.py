from json import JSONDecodeError
from typing import Dict, Any

import frontmatter
import os
from dotenv import load_dotenv
import json
from backend.src.utils.logger_utils import logger


def read_skill(file_path: str):
    # Parse the SKILL markdown file and return as dir
    with open(file_path, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)

    # Extract metadata and instructions
    skill_name = post.get('name', 'Default Skill')
    skill_instructions = post.content  # This is the actual Markdown body
    return {
        "skill_name": skill_name,
        "skill_instructions": skill_instructions
    }


def construct_user_prompt(rag_source: str, linear_source: str, user_query: str):
    return f"""**summary RAG** \'{rag_source.strip()}\'
**summary Linear** \'{linear_source.strip()}\'
**user query** {user_query}"""


def json_str2dir(json_str: str) -> Dict[str, Any] | None:
    try:
        data = json.loads(json_str)
    except JSONDecodeError:
        logger.error(f"Error during parsing result {json_str}")
        return None
    return data


class Properties:
    def __init__(self):
        # Load key-value pairs from the .env file into environment variables
        load_dotenv()
        # Safely extract hidden credentials
        self.db_host = os.getenv("DB_HOST")
        self.db_username = os.getenv("DB_USERNAME")
        self.db_password = os.getenv("DB_PASSWORD")
        self.db_schema = os.getenv("DB_SCHEMA")
        self.linear_api_key = os.getenv("LINEAR_API_KEY")

        # # Use them in your application logic
        # logger.debug(f"DB_HOST {self.db_host}")
        # logger.debug(f"DB_USERNAME {self.db_username}")
        # logger.debug(f"DB_PASSWORD {self.db_password}")
        # logger.debug(f"DB_SCHEMA {self.db_schema}")
        # logger.debug(f"LINEAR_API_KEY {self.linear_api_key}")


# Create a single global object here
my_properties = Properties()
MODEL = 'llama3.2'
CHAT_NAME = "ollama_chat"
