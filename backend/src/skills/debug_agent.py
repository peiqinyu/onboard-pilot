# Debug Class
import ollama
from backend.src.skills.base_agent import BaseAgent
from backend.src.memory.logger_utils import logger
import asyncio


class DebugAgent(BaseAgent):
    def __init__(self):
        name = "Debug"
        usage_prompt = f"""**{name}**: 
Use this category if the user's query contains ANY code, technical architecture, or GitHub links.
Triggers for `{name}` include:
1. Asking to explain, understand, summarize, or review a piece of code (e.g., "what is this code about").
2. Troubleshooting, fixing errors, or debugging.
3. Questions about a codebase, file, or code logic.

CRITICAL RULE: 
- If the user provides a code snippet (e.g., using ``` code blocks) or a GitHub URL, it MUST be 
classified as `{name}`. Do not evaluate whether the code is complete, correct, or too short—if code exists in the 
prompt, it is `{name}`. 
- If the query is a high-level, conceptual question about processes, workflows, or technical 
capabilities WITHOUT a provided code snippet or error trace, do NOT classify it as Debug. Route it to Research 
instead. 
"""
        super().__init__(name,
                         "Use this skill when asked to debug code for bugs and style",
                         usage_prompt,
                         "debug_karpathy")

    def init_system_prompt(self):
        self.system_prompt = f"""You are an AI acting with the following 
        skill directives:\n{self.skill_instructions}"""

    def run_skill_with_ollama(self, user_query: str):
        # 1. Construct the system prompt using the Markdown content
        system_prompt = f"You are an AI acting with the following skill directives:\n\n{self.skill_instructions}"

        logger.info(f"🧬 Executing Skill: [{self.name}] via Ollama...")

        # 2. Call the Ollama API
        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': user_query
                }
            ],
            options={
                'temperature': 0.2  # Keeps the model focused on the skill instructions
            }
        )

        # 3. Extract and return the text response
        return response['message']['content']


if __name__ == "__main__":
    # Example execution
    agent = DebugAgent()
    # user_input1 = "Review this function: def compute(x): return x * 2"
    # result1 = agent.run_skill_with_ollama(user_input1)
    # logger.debug(result1)
    user_input = "Debug this function: def compute(x): return x / 0"
    # result2 = agent.run_skill_with_ollama(user_input2)
    # logger.debug(result2)
    agent.add_user_message(user_input)
    asyncio.run(agent.answer_question())
    agent.add_user_message("how about if I change it to /2?")
    asyncio.run(agent.answer_question())
