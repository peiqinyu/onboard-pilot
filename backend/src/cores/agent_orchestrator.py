from json import JSONDecodeError

from backend.src.memory.utils import MODEL
from backend.src.memory.pg_vector_rag_connector import PgVectorRAGStoreConnector
from backend.src.skills.base_agent import BaseAgent
from backend.src.skills.debug_agent import DebugAgent
from backend.src.skills.report_agent import ReportAgent
from backend.src.skills.research_agent import ResearchAgent
import ollama
import json
import re
from backend.src.memory.logger_utils import logger
from backend.src.memory.utils import my_properties


class AgentOrchestrator:
    def __init__(self):
        format_prompt = f"""Respond EXACTLY in this JSON format, with no additional text, markdown blocks, 
        or formatting: {{ "type": "<Debug, Research, or Other>", "explanation": "<Briefly explain your exact 
        reasoning for why you chose this specific category based on the user's prompt with triple quotes, 
        remove special characters if any>" }} --- """
        other_prompt = """**Other**: 
                Use this category ONLY for general conversation, greetings, or entirely non-technical topics (e.g., "hello", "how are you", or asking about the weather).

                CRITICAL EXCLUSION: You MUST NOT select "Other" if the user's prompt contains ANY of the following:
                - Code snippets (e.g., ```python)
                - Technical development questions
                - GitHub links
                - Requests to explain code logic
                If the prompt contains any code, no matter how short, it belongs in another category, NEVER "Other"."""

        self.system_prompt = f"""You are a technical communication expert analyze user's intention. 
                                       Please analyze user's question, and classify the user's 
                                       intention into one of the following types:
        """ + format_prompt + other_prompt
        self.agent_dir = {}
        self.model = MODEL
        # Identify domain-specific terms to preserve
        self.technical_terms = [
            "api",
            "sdk",
            "cli",
            "ui",
            "ux",
            "git",
            "docker",
            "kubernetes",
            "k8s",
            "azure",
            "aws",
            "gcp",
            "cloud",
            "devops",
            "ci/cd",
            "pipeline",
            "semantic kernel",
            "llm",
            "openai",
            "gpt",
            "embedding",
            "vector",
            "database",
            "storage",
            "memory",
            "cache",
            "index",
            "search",
            "authentication",
            "authorization",
            "security",
            "encryption",
            "documentation",
            "markdown",
            "slack",
            "teams",
            "chat",
            "bot",
            "function",
            "method",
            "class",
            "object",
            "interface",
            "skill",
        ]

        # Remove question words and common filler words
        self.question_words = [
            "what",
            "how",
            "why",
            "when",
            "where",
            "who",
            "is",
            "are",
            "can",
            "could",
            "would",
            "should",
        ]
        self.filler_words = [
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
            "about",
            "like",
            "as",
            "of",
        ]
        self.rag = PgVectorRAGStoreConnector()

    def register_skill(self, agent: BaseAgent):
        self.agent_dir[agent.name] = agent
        self.system_prompt = self.system_prompt + "\n" + agent.usage_prompt

    def assign_agent(self, user_query: str) -> tuple[BaseAgent, str] | None:
        # analyze the user's intention to debug, research or OTHER
        # logger.debug(f"Assigning agent with [{self.system_prompt}]")
        query_type_json = ollama.chat(
            model=self.model,
            messages=[
                {
                    'role': 'system',
                    'content': self.system_prompt
                },
                {
                    'role': 'user',
                    'content': user_query
                }
            ],
            options={
                'temperature': 0.0  # Keeps the model focused on the skill instructions
            }
        )['message']['content']
        try:
            data = json.loads(query_type_json)
            # and grab the corresponding agent:
            agent = self.agent_dir.get(data['type'])
            # logger.info(f"""Ask type: **{data['type']}**
# explanation: {data['explanation']}""")
            if agent is not None:
                logger.debug(f"""agent assign: agent[{agent.name}]""")
                return agent, data['explanation']
            else:
                logger.warning(f"""Please ask technical related question""")
                return None, 'No related skill found'
        except JSONDecodeError:
            logger.error(f"AgentOrchestrator Error during parsing result {query_type_json}")

    def filter_words(self, user_query: str) -> str:
        processed = user_query.lower()
        # Only remove these words if they're standalone (not part of another word)
        words = processed.split()
        filtered_words = []
        for word in words:
            # Remove punctuation for comparison
            clean_word = re.sub(r"[^\w\s]", "", word)

            # Preserve technical terms
            if any(term == clean_word for term in self.technical_terms):
                filtered_words.append(word)
                continue

            # Filter out question words and filler words
            if clean_word not in self.question_words and clean_word not in self.filler_words:
                filtered_words.append(word)

            # If we've removed too many words, use the original query
        if len(filtered_words) < len(words) / 2:
            logger.info(f"Too many words removed, using original query: {user_query}")
            return user_query

        processed_query = " ".join(filtered_words)
        logger.info(f"⚙️ Preprocessed query [{processed_query}]\n Origin Query[{user_query}]")
        return processed_query


if __name__ == "__main__":
    logger.debug(my_properties.linear_api_key)
    orchestrator = AgentOrchestrator()
    researchAgent = ResearchAgent()
    debugAgent = DebugAgent()
    reportAgent = ReportAgent()
    orchestrator.register_skill(researchAgent)
    orchestrator.register_skill(debugAgent)
    orchestrator.register_skill(reportAgent)
    logger.debug(f"""system prompt {orchestrator.system_prompt}""")
    orchestrator.chat("how's the weather today")
    orchestrator.chat("what is the testing process")
    orchestrator.chat("what is this code about ```python def compute(x): Compute the value of x.")
