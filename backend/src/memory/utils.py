from json import JSONDecodeError
from typing import Dict, Any, List
from pathlib import Path
import frontmatter
import os
from dotenv import load_dotenv
import json

from pyarrow.lib import ArrowInvalid

from backend.src.memory.logger_utils import logger
import pandas as pd
from pandas import DataFrame


def read_skill(file_path: str):
    # Parse the SKILL markdown file and return as dir
    with open(file_path, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)

    # Extract metadata and instructions
    skill_instructions = post.content  # This is the actual Markdown body
    return {
        "skill_instructions": skill_instructions
    }


def read_file(file_path: str):
    # Parse the SKILL markdown file and return as dir
    with open(file_path, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)

    """
        Extracts the file name with extension from a full path string.
        Example: "xx/data/src/file.txt" -> "file.txt"
    """
    file_name = Path(file_path).name

    file_content = post.content  # This is the actual content body
    return {
        "file_name": file_name,
        "file_content": file_content
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


def load_raga_parquet(file_path: str,
                      selected_cols: List[str] | None = None) -> DataFrame | None:
    """
    read dataset in https://huggingface.co/datasets/dwb2023/ragas-golden-dataset/blob/main/data/train-00000-of-00001.parquet
    :param selected_cols:
    :param file_path:
    :return:
    """
    if selected_cols is None:
        # Read a single Parquet file
        return pd.read_parquet(file_path)
    else:
        try:
            # Read only specific columns to save memory
            return pd.read_parquet(file_path, columns=selected_cols)
        except ArrowInvalid:
            return None


# Create a single global object here
my_properties = Properties()
MODEL = 'llama3.1'  # 'llama3.2'
CHAT_NAME = "ollama_chat"


if __name__ == "__main__":
    # data_dir = str(Path(__file__).parent.resolve()) + os.sep + '..' + os.sep + 'data'
    # file1 = data_dir + os.sep + 'google_java_style_guideline1'
    # f = read_file(file1)
    # print(f)
    file_loc = str(Path(__file__).parent.resolve()) + os.sep \
               + '..' + os.sep + '..' \
               + os.sep + 'tests'\
               + os.sep + 'golden_dataset' \
               + os.sep + 'train-00000-of-00001.parquet'
    f = load_raga_parquet(file_loc, ['user_input',
                                     'reference_contexts',
                                     'reference'])
    print(f)

