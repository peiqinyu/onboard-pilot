import os
import json
from pathlib import Path
import pandas as pd
from backend.src.manage import get_chat_responses
from langchain_ollama import ChatOllama
import os
from datetime import datetime
from backend.src.memory.utils import load_raga_parquet

CLAIM_MODEL = 'llama3.1'
EVA_MODEL = 'llama3.1'
generate_report = False


def _answers2claims(answer: str) -> list[str]:
    # Uses your free, local Ollama model as the judge
    claim_extractor = ChatOllama(model=CLAIM_MODEL, temperature=0.0)

    prompt = f"""Task: Deconstruct the following text into a list of independent, atomic claims.
Rules:
    1. Each statement must contain only one single fact or idea.
    2. Split compound sentences or lists into separate bullet points ONLY if they are explicitly stated in the text.
    3. STRICT LITERAL ADHERENCE: Use the exact phrasing, entities, and scope from the original text. Do not paraphrase, expand, or introduce outside assumptions (e.g., if a word like "investment" is part of a direct list, keep the claim tightly bound to what the text actually stated about it without extrapolating).
    4. Do not add outside information.
    5. Keep the original meaning of the text.
    6. Output ONLY a plain markdown bulleted list using dashes (-). Do not wrap the output in JSON, do not add headers, and do not include any introductory or conversational text.

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


def check_faithfulness_locally_v1(context: str, claim_list: list[str]) -> dict:
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

    prompt = f"""You are an expert evaluation judge. 
    Evaluate the faithfulness of the generated claims based on the provided context.

    Context:
    {context}

    Claims to evaluate:
    {claim_list}

    Evaluation Steps:
    1. Break down the text into distinct individual claims.
    2. For each claim, determine if it is supported by the context (true or false). 
       CRITICAL RULE: You MUST accept claims that use synonyms, paraphrasing, or logical equivalents (e.g., "surge" means "increase"). Do not require exact word matches. If the meaning is entailed by the context, mark it as true.
    3. Count the Total Number of Claims.
    4. Count the Number of Supported Claims.
    5. Calculate the final score precisely: (Supported Claims) / (Total Claims).

    Output a JSON object with EXACTLY these keys:
    - "claims_evaluated": [list of each claim and its boolean support status]
    - "total_claims": (integer)
    - "supported_claims": (integer)
    - "score": (float)
    - "reason": "A short explanation of which claims were unsupported. If all are supported, write 'All claims supported'."
    """

    response = judge.invoke(prompt)
    return json.loads(response.content)


def check_faithfulness_locally(user_query: str, retrieved_context: str, answer: str, claim_list: list[str]) -> dict:
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

    prompt = f"""You are an expert AI evaluator. Your job is to strictly evaluate a RAG (Retrieval-Augmented 
        Generation) system across faithfulness dimension. 

    ### INPUTS PROVIDED:
    1. User Query: {user_query}
    2. Retrieved Context/Chunk: {retrieved_context}
    3. Generated Answer: {answer}
    4. Extracted Claims to Evaluate: {claim_list}

    ### EVALUATION STEPS:
    FAITHFULNESS / GROUNDEDNESS (Extracted Claims vs. Context)
        - Used individual claims from "Extracted Claims to Evaluate".
        - For each claim, determine if it is supported by the context (true or false). 
           CRITICAL RULE: You MUST accept claims that use synonyms, paraphrasing, or logical equivalents (e.g., "surge" means "increase"). Do not require exact word matches. If the meaning is entailed by the context, mark it as true.
        - Count the Total Number of Claims.
        - Count the Number of Supported Claims.
        - Calculate the final score precisely: (Supported Claims) / (Total Claims).

    ### OUTPUT FORMAT:
    Output a JSON object with EXACTLY these keys. Do not include markdown formatting outside the JSON block.

    {{
      "faithfulness": {{
        "claims_evaluated": "[List of each generated claim and its boolean support status against context]",
        "score": "(float between 0.0 and 1.0)",
        "reason": "Short explanation of unsupported claims or 'All claims supported'."
      }}
    }}
    """

    response = judge.invoke(prompt)
    return json.loads(response.content)


def check_answer_relevance_locally(user_query: str, retrieved_context: str, answer: str, claim_list: list[str]) -> dict:
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

    prompt = f"""You are an expert AI evaluator. Your job is to strictly evaluate a RAG (Retrieval-Augmented 
    Generation) system across the answer relevance dimension. 

    ### INPUTS PROVIDED:
    1. User Query: {user_query}
    2. Retrieved Context/Chunk: {retrieved_context}
    3. Generated Answer: {answer}
    4. Extracted Claims to Evaluate: {claim_list}

    ### EVALUATION STEPS: ANSWER RELEVANCE (Extracted Claims vs. Query) 1. Review the list of Extracted Claims 
    provided in the inputs. 2. For each claim, determine if it directly addresses, expands upon, or helps answer the 
    User Query (true/false). - CRITICAL RULE 1: Ignore whether the claim is factually true or false. Focus entirely 
    on whether it is on-topic and helpful to the user's specific question. - CRITICAL RULE 2: Evaluate ONLY the 
    claims provided in the list. Do not extract new claims. 3. Count the Total Number of Claims provided. 4. Count 
    the Number of Relevant Claims (where status is true). 5. Calculate the final score precisely using this formula: 
    (Number of Relevant Claims) / (Total Number of Claims). If Total is 0, score is 0.0. Ensure the score is strictly 
    a float between 0.0 and 1.0. 

    ### OUTPUT FORMAT:
    Output a JSON object with EXACTLY these keys. Do not wrap the JSON in markdown code blocks (no ```json).

    {{
      "answer_relevance": {{
        "claims_evaluated": [List of each claim and its boolean relevance status, e.g., {{"claim": "...", "relevant": true}}],
        "total_claims": (integer),
        "relevant_claims": (integer),
        "score": (float strictly between 0.0 and 1.0),
        "reason": "Short explanation of off-topic claims or 'All claims relevant'."
      }}
    }}
    """

    response = judge.invoke(prompt)
    return json.loads(response.content)


def check_context_precision_locally(user_query: str, retrieved_context: str, answer: str, claim_list: list[str]) -> dict:
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

    prompt = f"""You are an expert AI evaluator assessing Context Precision for a RAG system.

    ### INPUTS:
    1. User Query: {user_query}
    2. Retrieved Context Chunk: {retrieved_context}
    3. Generated Answer: {answer}

    ### EVALUATION INSTRUCTIONS:
    Context precision measures whether the retrieved context contains the necessary information to answer the query, without penalizing standard chunk sizes that contain natural background text.

    1. **Check Utility:** Does the retrieved context contain the core facts needed to formulate the correct answer? (If yes, it is relevant).
    2. **Accept Noise Tolerance:** A retrieved chunk naturally contains surrounding context or background sentences. Do NOT penalize the chunk for minor background text or filler sentences, *unless* the chunk is completely off-topic or entirely irrelevant to the query.
    3. **Calculate Score:** 
       - Assign **1.0** if the chunk successfully provides the core information needed for the answer.
       - Assign **0.0** if the chunk is completely irrelevant or fails to support the answer.

    ### OUTPUT FORMAT:
    Output a JSON object with EXACTLY these keys:
    {{
      "context_precision": {{
        "is_relevant": (boolean true/false),
        "score": (float 1.0 or 0.0),
        "reason": "Explain why the context supports the answer, ignoring minor background noise."
      }}
    }}
    """

    response = judge.invoke(prompt)
    return json.loads(response.content)


def check_scores_locally(user_query: str, retrieved_context: str, answer: str, claim_list: list[str]) -> dict:
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

    prompt = f"""You are an expert AI evaluator. Your job is to strictly evaluate a RAG (Retrieval-Augmented 
        Generation) system across three distinct dimensions. 

    ### INPUTS PROVIDED:
    1. User Query: {user_query}
    2. Retrieved Context/Chunk: {retrieved_context}
    3. Generated Answer: {answer}
    4. Extracted Claims to Evaluate: {claim_list}

    ### EVALUATION STEPS:

    1. FAITHFULNESS / GROUNDEDNESS (Extracted Claims vs. Context)
        - Used individual claims from "Extracted Claims to Evaluate".
        - For each claim, determine if it is supported by the context (true or false). 
           CRITICAL RULE: You MUST accept claims that use synonyms, paraphrasing, or logical equivalents (e.g., "surge" means "increase"). Do not require exact word matches. If the meaning is entailed by the context, mark it as true.
        - Count the Total Number of Claims.
        - Count the Number of Supported Claims.
        - Calculate the final score precisely: (Supported Claims) / (Total Claims).

    2. ANSWER RELEVANCE (Extracted Claims vs. Query)
        - Review the list of Extracted Claims provided in the inputs.
        - For each claim in the list, determine if it directly addresses, expands upon, or helps answer the User Query (True/False).
            - CRITICAL RULE 1: Ignore whether the claim is factually true or false. Focus entirely on whether it is on-topic and helpful to the user's specific question.
            - CRITICAL RULE 2: Evaluate ONLY the claims provided in the list. Do not extract new claims.
        - Count the total number of claims provided in the list.
        - Count the number of relevant claims.
        - Calculate the score precisely: (Relevant Claims) / (Total Claims).
        
    3. CONTEXT PRECISION (Context vs. Query)
        - Break down the Retrieved Context/Chunk into individual facts or key sentences.
        - For each fact/sentence in the context, determine if it is relevant to answering the User Query (True/False).
        - Calculate Score: (Relevant Context Sentences) / (Total Context Sentences).

    ### OUTPUT FORMAT:
    Output a JSON object with EXACTLY these keys. Do not include markdown formatting outside the JSON block.

    {{
      "faithfulness": {{
        "claims_evaluated": "[List of each generated claim and its boolean support status against context]",
        "score": "(float between 0.0 and 1.0)",
        "reason": "Short explanation of unsupported claims or 'All claims supported'."
      }},
      "answer_relevance": {{
        "claims_evaluated": "[List of each generated claim and its boolean relevance status against query]",
        "score": "(float between 0.0 and 1.0)",
        "reason": "Short explanation of off-topic claims or 'All claims relevant'."
      }},
      "context_precision": {{
        "sentences_evaluated": "[List of context sentences and their boolean relevance status against query]",
        "score": "(float between 0.0 and 1.0)",
        "reason": "Short explanation of noisy/irrelevant context included."
      }}
    }}
    """

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
    c_list = []  # context list
    raga_ctx = ""
    if top_k is None:
        for idx, r in df.iterrows():
            q = r["user_input"]
            q_list.append(q)
            context = r['reference'] + "\n" + r['reference_contexts']
            # raga_ctx = raga_ctx + "\n" + context
            c_list.append(context)
    else:
        for idx, r in df.head(top_k).iterrows():
            q = r["user_input"]
            q_list.append(q)
            context = r['reference'] + "\n" + r['reference_contexts']
            # raga_ctx = raga_ctx + "\n" + context
            c_list.append(context)
    return q_list, c_list


if __name__ == "__main__":
    # --- How to use it in your test script ---
    # df = pd.read_csv("golden_dataset/evaluation_dataset1.csv")[:10]

    # for index, row in df.iterrows():
    #     question = row["question"]
    #     question_list.append(question)

    # self_question_list = load_self_doc(2)
#     self_context = """dataset was created using information in [Google Java Guideline](https://google.github.io/styleguide/javaguide.html)
# # and [OpenAI Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices) against RAG.
# # """

    ragas_question_list, ragas_context_list = load_ragas_doc(2)

    faithfulness_total_score = 0
    answer_relevance_total_score = 0
    context_precision_total_score = 0
    question_list = ragas_question_list

    # print(f"""QUESTION LIST:[ {question_list}]\nCONTEXT [{ctx}]""")
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
        ctx = f"""**Context1** [{ragas_context_list[i]}]"""
        ques = question_list[i]
        faithfulness_res = check_faithfulness_locally_v1(
            context=ctx,
            claim_list=clms,
        )
        # total_score += res["score"]
        # res = check_scores_locally(
        #     user_query=ques,
        #     retrieved_context=ctx,
        #     claim_list=clms,
        #     answer=ans
        # )

        # faithfulness_res = check_faithfulness_locally(
        #     user_query=ques,
        #     retrieved_context=ctx,
        #     claim_list=clms,
        #     answer=ans
        # )
        answer_relevance_res = check_answer_relevance_locally(
            user_query=ques,
            retrieved_context=ctx,
            claim_list=clms,
            answer=ans
        )
        context_precision_res = check_context_precision_locally(
            user_query=ques,
            retrieved_context=ctx,
            claim_list=clms,
            answer=ans
        )

        # Format the console string
        print(f"## Question-{i + 1}")
        print(f"**Faithfulness Evaluation Result**: {faithfulness_res}")
        print(f"**Answer Relevance Evaluation Result**: {answer_relevance_res}")
        print(f"**Context Precision Evaluation Result**: {context_precision_res}")
        print(f"**Question**: {question_list[i]}")
        print(f"**Answer**: {ans}")
        print(f"**Claims**: {clms}")
        print(f"**Source**: {src}")
        # faithfulness_score = faithfulness_res["faithfulness"]["score"]
        faithfulness_score = faithfulness_res["score"]
        answer_relevance_score = answer_relevance_res["answer_relevance"]["score"]
        context_precision_score = context_precision_res["context_precision"]["score"]
        faithfulness_total_score += faithfulness_score
        answer_relevance_total_score += answer_relevance_score
        context_precision_total_score += context_precision_score
        print(f"**Faithfulness Score**: {faithfulness_score}")
        try:
            # reasoning_str = f"**Reasoning**:{res['reason']}"
            # faithfulness_reason_str = faithfulness_res["faithfulness"]["reason"]
            faithfulness_reason_str = faithfulness_res["reason"]
        except KeyError:
            faithfulness_reason_str = "**Reasoning**:No Faithfulness Reason generated somehow..."
        print(faithfulness_reason_str)

        print(f"**Answer Relevance Score**: {answer_relevance_score}")
        try:
            answer_relevance_reason_str = answer_relevance_res["answer_relevance"]["reason"]
        except KeyError:
            answer_relevance_reason_str = "**Reasoning**:No Answer Relevance Reason generated somehow..."
        print(answer_relevance_reason_str)

        print(f"**Context Precision Score**: {context_precision_score}")
        try:
            context_precision_reason_str = context_precision_res["context_precision"]["reason"]
        except KeyError:
            context_precision_reason_str = "**Reasoning**:No Context Precision Reason generated somehow..."
        print(context_precision_reason_str)

        print("--------------------------------------------------------------------")

        # 2. Write to markdown file if flag is True
        if generate_report:
            report_file.write(f"## Question-{i + 1}\n")
            report_file.write(f"**Question**: {question_list[i]}\n")
            report_file.write(f"**Answer**: {ans}\n")
            report_file.write(f"**Claims**: {clms}\n")
            report_file.write(f"**Source**: {src}\n")
            report_file.write(f"**Faithfulness**: {faithfulness_score}\n")
            report_file.write(f"**Score**: {faithfulness_score}\n")
            report_file.write(f"**Reason**: {faithfulness_reason_str}\n")
            report_file.write(f"**Details**: {faithfulness_res}\n")

            report_file.write(f"**Answer Relevance Score**: {answer_relevance_score}\n")
            report_file.write(f"**Answer Relevance Reason**: {answer_relevance_reason_str}\n")
            report_file.write(f"**Answer Relevance Details**: {answer_relevance_res}\n")

            report_file.write(f"**Context Precision Score**: {context_precision_score}\n")
            report_file.write(f"**Context Precision Reason**: {context_precision_reason_str}\n")
            report_file.write(f"**Context Precision Details**: {context_precision_res}\n")

            report_file.write(f"\n{'-' * 68}\n\n")

    faithfulness_avg_score = faithfulness_total_score / len(generated_answers)
    answer_relevance_avg_score = answer_relevance_total_score / len(generated_answers)
    context_precision_avg_score = context_precision_total_score / len(generated_answers)

    print(f"Average Faithfulness Score {faithfulness_avg_score}")
    print(f"Average Answer Relevance Score {answer_relevance_avg_score}")
    print(f"Average Context Precision Score {context_precision_avg_score}")

    # 3. Append summary and close file if flag is True
    if generate_report:
        report_file.write(f"## Summary\n")
        report_file.write(f"**Average Faithfulness Score**: {faithfulness_avg_score:.4f}\n")
        report_file.write(f"**Average Answer Relevance Score**: {answer_relevance_avg_score:.4f}\n")
        report_file.write(f"**Average Context Precision Score**: {context_precision_avg_score:.4f}\n")
        report_file.close()
        print(f"Report saved to: {filename}")
