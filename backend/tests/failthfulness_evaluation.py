import os
import json
from pathlib import Path
import pandas as pd
from backend.src.manage import get_chat_responses
from langchain_ollama import ChatOllama
import os
from datetime import datetime
from backend.src.memory.utils import load_raga_parquet

EVA_MODEL = 'llama3.1'
generate_report = True


def _answers2claims(answer: str) -> list[str]:
    # Uses your free, local Ollama model as the judge
    claim_extractor = ChatOllama(model=EVA_MODEL, temperature=0.0)

    prompt = f"""Task: Deconstruct the following text into a list of independent, atomic claims.

Rules:
1. Each statement must contain only one single fact or idea.
2. Split compound sentences into separate bullet points.
3. Do not add outside information or assumptions.
4. Keep the original meaning of the text.
5. Output ONLY a plain markdown bulleted list using dashes (-). Do not wrap the output in JSON, do not add headers, and do not include any introductory or conversational text.

Text to break down: {answer}"""

    response = claim_extractor.invoke(prompt)
    raw_output = response.content
    # Parse the raw text string into a clean Python list of strings
    claims_list = []
    for line in raw_output.split("\n"):
        cleaned_line = line.strip()
        # Look for lines starting with typical markdown bullet markers
        if cleaned_line.startswith(("-", "*", "•")) or (
                len(cleaned_line) > 2 and cleaned_line[0].isdigit() and cleaned_line[1] == '.'):
            # Strip out the leading bullet marker to get just the text
            if cleaned_line[0].isdigit():
                # Handles cases where it outputs numbered lists like "1. claim"
                claim_text = cleaned_line.split(".", 1)[-1].strip()
            else:
                claim_text = cleaned_line.lstrip("-*• ").strip()

            if claim_text:
                claims_list.append(claim_text)

    return claims_list


def check_faithfulness_locally(context: str, claim_list: list[str]) -> dict:
    # claim_list = _answers2claims(answer)
    print(f"""Processing {len(claim_list)} claims...""")
    if not claim_list or len(claim_list) == 0:
        return {
            "claims_evaluated": [],
            "total_claims": 0,
            "supported_claims": 0,
            "score": 0.0,
            "reason": "No claims were found or extracted from the answer to evaluate."
        }
    # Use llama3.1 if you have it pulled for better reasoning, or keep llama3.2
    judge = ChatOllama(model=EVA_MODEL, format="json", temperature=0.0)

    prompt = f"""You are a strict evaluation judge. 
Evaluate the faithfulness of the generated claims based strictly on the provided context.

Context:
{context}

Claims to evaluate:
{claim_list}

Evaluation Steps:
1. Break down the text into distinct individual claims.
2. For each claim, determine if it is directly supported by the context (true or false).
3. Count the Total Number of Claims.
4. Count the Number of Supported Claims.
5. Calculate the final score precisely using this formula: (Number of Supported Claims) / (Total Number of Claims). If Total is 0, score is 0.0. Ensure the final score is strictly between 0.0 and 1.0.

Output a JSON object with EXACTLY these keys:
- "claims_evaluated": [list of each claim and its boolean support status]
- "total_claims": (integer)
- "supported_claims": (integer)
- "score": (float strictly between 0.0 and 1.0)
- "reason": "A short explanation of which claims were unsupported or hallucinated"

JSON Output:"""

    response = judge.invoke(prompt)
    return json.loads(response.content)


def load_self_doc(top_k: int | None = None) -> list[str]:
    if top_k is None:
        df_doc = pd.read_csv("golden_dataset/evaluation_dataset1.csv")[:top_k]
    else:
        df_doc = pd.read_csv("golden_dataset/evaluation_dataset1.csv")
    questions = []
    for n, r in df_doc.iterrows():
        q = r["question"]
        questions.append(q)
    return questions


def load_ragas_doc(top_k: int | None = None):
    file_loc = str(Path(__file__).parent.resolve()) \
               + os.sep + 'golden_dataset' \
               + os.sep + 'train-00000-of-00001.parquet'
    df = load_raga_parquet(file_loc, ['user_input',
                                      'reference_contexts',
                                      'reference'])
    q_list = []
    raga_ctx = ""
    if top_k is None:
        for idx, r in df.iterrows():
            q = r["user_input"]
            q_list.append(q)
            raga_ctx = raga_ctx + "\n" + r['reference'] + "\n" + r['reference_contexts']
    else:
        for idx, r in df.head(top_k).iterrows():
            q = r["user_input"]
            q_list.append(q)
            raga_ctx = raga_ctx + "\n" + r['reference'] + "\n" + r['reference_contexts']
    return q_list, raga_ctx


if __name__ == "__main__":
    # --- How to use it in your test script ---
    # df = pd.read_csv("golden_dataset/evaluation_dataset1.csv")[:10]

    # for index, row in df.iterrows():
    #     question = row["question"]
    #     question_list.append(question)

    # self_question_list = load_self_doc(2)
    self_context = """dataset was created using information in [Google Java Guideline](https://google.github.io/styleguide/javaguide.html)
# and [OpenAI Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices) against RAG.
# """

    ragas_question_list, ragas_context = load_ragas_doc(10)

    total_score = 0
    question_list = ragas_question_list

    ctx = f"**Context1** [{self_context}],\n **context2** [{ragas_context}] "
    # ctx = ragas_context
    print(f"""QUESTION LIST:[ {question_list}]\nCONTEXT [{ctx}]""")
    generated_answers = get_chat_responses(question_list)

    # 1. Generate the timestamp and dynamic filename if report generation is active
    if generate_report:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join("reports", f"evaluation_report_{timestamp}.md")

        # Open and initialize the file with a header
        report_file = open(filename, "w", encoding="utf-8")
        report_file.write(f"# Evaluation Report\n")
        report_file.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for i in range(len(generated_answers)):
        resp = generated_answers[i]
        ans = resp[0]
        src = resp[1]
        clms = _answers2claims(ans)
        res = check_faithfulness_locally(
            context=ctx,
            claim_list=clms
        )
        total_score += res["score"]

        # Format the console string
        print(f"## Question-{i + 1}")
        print(f"**Question**: {question_list[i]}")
        print(f"**Answer**: {ans}")
        print(f"**Claims**: {clms}")
        print(f"**Source**: {src}")
        print(f"**Faithfulness Score**: {res['score']}")

        try:
            reasoning_str = f"**Reasoning**:{res['reason']}"
        except KeyError:
            reasoning_str = "**Reasoning**:No Reason generated somehow..."

        print(reasoning_str)
        print("--------------------------------------------------------------------")

        # 2. Write to markdown file if flag is True
        if generate_report:
            report_file.write(f"## Question-{i + 1}\n")
            report_file.write(f"* **Question**: {question_list[i]}\n")
            report_file.write(f"* **Answer**: {ans}\n")
            report_file.write(f"* **Claims**: {clms}\n")
            report_file.write(f"* **Source**: {src}\n")
            report_file.write(f"* **Faithfulness Score**: {res['score']}\n")
            report_file.write(f"* {reasoning_str}\n")
            report_file.write(f"\n{'-' * 68}\n\n")

    avg_score = total_score / len(generated_answers)
    print(f"Average Score {avg_score}")

    # 3. Append summary and close file if flag is True
    if generate_report:
        report_file.write(f"## Summary\n")
        report_file.write(f"**Average Faithfulness Score**: {avg_score:.4f}\n")
        report_file.close()
        print(f"Report saved to: {filename}")
