# Report Class
from datetime import datetime
import ollama
from backend.src.skills.base_agent import BaseAgent
from backend.src.memory.logger_utils import logger
import asyncio

from backend.src.memory.utils import construct_user_prompt, json_str2dir


class ReportAgent(BaseAgent):
    def __init__(self):
        name = "Report"
        usage_prompt = f"""**{name}**:  If user's intention is to get a summary from content, it is a `{name}` type"""
        super().__init__(name,
                         "Use this skill when asked to report back to user",
                         usage_prompt,
                         "report")

    def init_system_prompt(self):
        self.system_prompt = f"""You are a technical communication expert writing elegant issue summaries for 
                               developers with the following skill directives:\n\n{self.skill_instructions}. 
                               Please read, combine and rewrite the following research summary to be clear, 
                    professional, and engaging for a developer audience.
                    """

    def beautified_summary(self, summary: str):
        """

        :param summary: format like this {
              "answer_found": true or false,
              "explanation": "If answer_found is false, put 'There is no related answer found'. If true, summarize the answer using ONLY the context.",
              "answer_detail": ""If answer_found is true, show the summarized answer"
              "source": "<Name of the source> and <the origin content of the source>, or null"
            }
        :return: formatted markdown
        """
        json_data = json_str2dir(summary)
        if json_data is None:
            return summary
        if json_data['answer_found'] == 'false':
            return f"""# 🤖 Executive Summary
## Sorry, no related answer found for your question. Please try asking something else.
---
*Report generated on {datetime.now().strftime('%Y-%m-%d')}*
"""
        json_data = json_str2dir(summary)
        if json_data is None:
            return summary
        if not json_data['answer_found']:
            return f"""# 🤖 Executive Summary
## Sorry, no related answer found for your question. Please try asking something else.
---
*Report generated on {datetime.now().strftime('%Y-%m-%d')}*
"""

        # Combine all parts into markdown
        markdown_content = f"""# 🤖 Executive Summary
## ✍️ Refined Insights
{json_data['answer_detail']}

## ✅ Why This Works
{json_data['explanation']}

## 🎯 Data Sources
{json_data['source']}
---

*Report generated on {datetime.now().strftime('%Y-%m-%d')}*
"""
        return markdown_content

    def run_report_research_with_ollama(self, research_output: str) -> str:
        system_prompt = f"""You are a technical communication expert writing elegant issue summaries for 
                               developers with the following skill directives:\n\n{self.skill_instructions}. 
                               Please read, combine and rewrite the following research summary to be clear, 
                    professional, and engaging for a developer audience.
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
                    'content': research_output
                }
            ],
            options={
                'temperature': 0.0  # Keeps the model focused on the skill instructions
            }
        )['message']['content']

        # json_data = json_str2dir(beautified_summary)

        return beautified_summary


if __name__ == "__main__":
    # Example execution
    agent = ReportAgent()
    query = "what is the testing process should be?"
    rag = """
        **Debugged Function**

        ```python
        def compute(x):
            Compute the value of x.
        """
    third_party = "this is a test issue, a feature for testing purpose"
    user_input = construct_user_prompt(rag, third_party, query)

    result1 = agent.run_report_research_with_ollama(query, rag, third_party)
    logger.debug(result1)
