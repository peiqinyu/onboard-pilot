# Research Class
from datetime import datetime
import ollama
from backend.src.skills.base_agent import BaseAgent
from backend.src.memory.logger_utils import logger
import asyncio


class ResearchAgent(BaseAgent):
    def __init__(self):
        name = "Research"
        usage_prompt = f"""**{name}**:  If the user's question is about architectural concepts, developer workflows, or processes, for example:
1. onboarding process
2. testing and continuous integration (CI) steps
3. deployment or continuous delivery (CD) pipelines
4. conceptual questions about what a system/pipeline can do
5. TODO lists for code development related items
it is a `{name}` type"""
        super().__init__(name,
                         "Use this skill when asked to research across knowledge base",
                         usage_prompt,
                         "research")

    def init_system_prompt(self):
        self.system_prompt = f"""{self.skill_instructions}"""

    def run_report_research_with_ollama(self, user_query: str,
                                        rag_summary: str, third_party_summary: str):
        system_prompt = f"""You are a technical communication expert writing elegant issue summaries for 
                               developers with the following skill directives:\n\n{self.skill_instructions}. 
                               Please read, combine and rewrite the following research summary to be clear, 
                    professional, and engaging for a developer audience.
                    **rag summary** \"\"\"{rag_summary.strip()}\"\"\" 
                    **third party summary** \"\"\"{third_party_summary.strip()}\"\"\"
                    """

        beautified_summary = ollama.chat(
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
                'temperature': 0.0  # Keeps the model focused on the skill instructions
            }
        )['message']['content']

        # Combine all parts into markdown
        markdown_content = f"""#Executive Summary

        ## Refined Summary Insights
        {beautified_summary}
        ---

        *Report generated on {datetime.now().strftime('%Y-%m-%d')}*
        """
        return markdown_content


if __name__ == "__main__":
    # Example execution
    agent = ResearchAgent()
    query = "how's the weather today"
    rag = """
    **Debugged Function**

    ```python
    def compute(x):
        Compute the value of x.
    """
    third_party = "this is a test issue, a feature for testing purpose"
    user_input = f"""**rag summary** \"\"\"{rag.strip()}\"\"\" 
                    **third party summary** \"\"\"{third_party.strip()}\"\"\""""
    agent.add_user_message(user_input)
    # asyncio.run(agent.answer_question())

    # result1 = agent.run_report_research_with_ollama(query, rag, third_party)
    # logger.info(result1)

