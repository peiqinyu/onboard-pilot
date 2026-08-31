import asyncio
import json
from semantic_kernel.exceptions import KernelServiceNotFoundError
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.ollama import OllamaChatCompletion, OllamaChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import KernelPlugin, KernelArguments
from backend.src.cores.agent_orchestrator import AgentOrchestrator
from backend.src.skills.debug_agent import DebugAgent
from backend.src.skills.report_agent import ReportAgent
from backend.src.skills.research_agent import ResearchAgent
from backend.src.memory.base_connector import BaseConnector
from backend.src.memory.linear_connector import LinearConnector
from backend.src.memory.logger_utils import logger
from backend.src.memory.pg_vector_rag_connector import PgVectorRAGStoreConnector
from backend.src.memory.utils import MODEL, CHAT_NAME, construct_user_prompt


def create_kernel(model: str, chat_name: str) -> Kernel:
    # 1. Initialize the Kernel
    kernel = Kernel()
    try:
        kernel.get_service(chat_name)
        logger.debug(f"Chat service {chat_name.upper()} available in kernel")
    except KernelServiceNotFoundError:
        logger.warning(f"No chat service {chat_name.upper()} available in kernel, initializing now...")
        # 2. Add Ollama as the core Chat Completion Service if not exist
        # By default, it looks for Ollama running at http://127.0.0.1:11434
        ollama_service = OllamaChatCompletion(
            ai_model_id=model,  # Replace with your local model name
            service_id=chat_name  # An internal moniker for tracking multiple models
        )
        kernel.add_service(ollama_service)
    logger.info(f"🤖 Kernel with llm {MODEL} chat service created successfully")
    return kernel


def register_all_skills() -> AgentOrchestrator:
    # register agents
    orchestrator = AgentOrchestrator()
    research_agent = ResearchAgent()
    debug_agent = DebugAgent()
    report_agent = ReportAgent()
    orchestrator.register_skill(research_agent)
    orchestrator.register_skill(debug_agent)
    orchestrator.register_skill(report_agent)
    logger.info(f"🤖 Agent orchestrator and registered to kernel, {len(orchestrator.agent_dir)} skills added")
    # for a_name in orchestrator.agent_dir:
    #     a = orchestrator.agent_dir[a_name]
    #     print(a)
    #     logger.debug(f"YOYO register agent {a.name} with prompt[{a.system_prompt}]")
    return orchestrator


def add_doc_plugin(kernel: Kernel, connector: BaseConnector) -> KernelPlugin:
    plugin_name = connector.name + "_connector"
    # register connector functions
    plugin = kernel.add_plugin(connector, plugin_name=plugin_name)
    # functions = kernel.add_plugin(linear_connector, plugin_name="linear_connector")
    logger.info(f"🤖 {connector.name.upper()} connector plugin added to kernel as {plugin_name}")
    return plugin


kernel_instance = create_kernel(MODEL, CHAT_NAME)
orchestrator_instance = register_all_skills()
rag_connector = PgVectorRAGStoreConnector()
linear_connector = LinearConnector()
rag_plugin = add_doc_plugin(kernel_instance, rag_connector)
linear_plugin = add_doc_plugin(kernel_instance, linear_connector)
chat_client = kernel_instance.get_service(CHAT_NAME)
settings = OllamaChatPromptExecutionSettings(options={"temperature": 0.2})


async def start_chat_session(kernel: Kernel, orchestrator: AgentOrchestrator):
    # Maintain a single ChatHistory object for this session
    history = ChatHistory()
    logger.info("🤖 AI Session Ready! Type 'exit' to quit.\n")
    current_agent_name = None
    # 3. Infinite loop handles an infinite number of questions dynamically
    while True:
        user_input = input("You: ")
        # Break condition
        if user_input.strip().lower() == "exit":
            print("Goodbye!")
            break

        if not user_input.strip():
            continue

        agent, explanation = orchestrator.assign_agent(user_input)
        if agent is None:
            print("I can answer technical related question only, please ask another question!")
            continue

        if current_agent_name is None or agent.name != current_agent_name:
            current_agent_name = agent.name
            # a new intention, clear old history
            # and use a new skill to handle
            history = ChatHistory()
            history.add_system_message(agent.system_prompt)
            logger.debug(f"🤖 (Re)Assign task to agent {agent.name}")
            # logger.debug(f"🤖 (Re)Assign task to agent {agent.name}, skill for {agent.system_prompt} added.")

        if current_agent_name == orchestrator.agent_dir["Research"].name:
            # grab related information from RAG and third party
            filtered_user_input = orchestrator.filter_words(user_input)

            # logger.debug(f"filtered out user input {filtered_user_input}")
            rag_search_function = rag_plugin["search_k_content"]
            rag_result = await kernel.invoke(
                function=rag_search_function,
                arguments=KernelArguments(query=filtered_user_input)
            )
            logger.debug(f"RAG results [{rag_result}]")

            linear_search_function = linear_plugin["search_k_content"]
            linear_result = await kernel.invoke(
                function=linear_search_function,
                arguments=KernelArguments(query=filtered_user_input)
            )
            logger.debug(f"Linear results [{linear_result}]")
            refined_user_input = construct_user_prompt(str(rag_result),
                                                       str(linear_result),
                                                       user_input)
        else:
            refined_user_input = user_input.strip()
        # Append the new user question
        history.add_user_message(refined_user_input)
        logger.debug(f"👩 refined user input: [{refined_user_input}]")

        try:
            # Await the response on the STILL-OPEN event loop
            response = await chat_client.get_chat_message_contents(
                chat_history=history,
                settings=settings
            )

            # Print and save the AI's answer so it remembers context
            ai_text = ""
            for chat_msg in response:
                chat_text = chat_msg.inner_content.message.content
                ai_text += chat_text

            print(f"\nAI: {ai_text}\n")
            history.add_assistant_message(ai_text)

        except Exception as e:
            logger.error(f"🚨An error occurred: {e}")


async def answer_questions(kernel: Kernel, orchestrator: AgentOrchestrator,
                           questions: list[str], agent_name: str | None = None,
                           enable_rag_search: bool = True,
                           enable_linear_search: bool = False) -> list[tuple]:
    # history = ChatHistory()
    # Maintain a single ChatHistory object for this session
    answers = []
    logger.info("🤖 AI chat created\n")
    current_agent_name = None
    # 3. Infinite loop handles an infinite number of questions dynamically
    for user_input in questions:
        history = ChatHistory()
        if not user_input.strip():
            no_agent_response = {
                "user_question": user_input,
                "response": None
            }
            logger.warning("User input is empty")
            answers.append((str(no_agent_response), None))
            continue
        if agent_name is None:
            agent, explanation = orchestrator.assign_agent(user_input)
            if agent is None:
                no_agent_response = {
                    "user_question": user_input,
                    "response": "I can answer technical related question only, please ask another question!"
                }
                logger.warning(no_agent_response)
                answers.append((str(no_agent_response), None))
                continue
        else:
            agent = orchestrator.agent_dir[agent_name]
            if agent is None:
                no_agent_response = {
                    "user_assigned_agent": agent_name,
                    "response": f"No agent found for {agent_name}!"
                }
                logger.warning(no_agent_response)
                answers.append((str(no_agent_response), None))
                continue

        if True:
        # if current_agent_name is None or agent.name != current_agent_name:
            current_agent_name = agent.name
            # a new intention, clear old history
            # and use a new skill to handle
            # history = ChatHistory()
            history.add_system_message(agent.system_prompt)
            logger.debug(f"🤖 (Re)Assign task to agent {agent.name}")
            # logger.debug(f"🤖 (Re)Assign task to agent {agent.name}, skill for {agent.system_prompt} added.")

        if current_agent_name == orchestrator.agent_dir["Research"].name:
            # grab related information from RAG and third party
            filtered_user_input = orchestrator.filter_words(user_input)
            if enable_rag_search:
                # logger.debug(f"filtered out user input {filtered_user_input}")
                rag_search_function = rag_plugin["search_k_content"]
                rag_result = await kernel.invoke(
                    function=rag_search_function,
                    arguments=KernelArguments(query=filtered_user_input)
                )
            else:
                rag_result = ""
            if enable_linear_search:
                linear_search_function = linear_plugin["search_k_content"]
                linear_result = await kernel.invoke(
                    function=linear_search_function,
                    arguments=KernelArguments(query=filtered_user_input)
                )
            else:
                linear_result = ""
            refined_user_input = construct_user_prompt(str(rag_result),
                                                       str(linear_result),
                                                       user_input)
        else:
            refined_user_input = user_input.strip()
        # Append the new user question
        history.add_user_message(refined_user_input)
        # logger.debug(f"👩 refined user input: [{refined_user_input}]")

        try:
            # logger.info(f"🤖 Agent: [{agent.name}] thinking...")
            # logger.debug(f"🤖 Agent: [{agent.name}] thinking with all messages [{history.messages}]...")
            # Await the response on the STILL-OPEN event loop
            response = await chat_client.get_chat_message_contents(
                chat_history=history,
                settings=settings
            )

            # Print and save the AI's answer so it remembers context
            ai_text = ""
            for chat_msg in response:
                chat_text = chat_msg.inner_content.message.content
                ai_text += chat_text

            # logger.debug(f"🤖 Agent AI text : [{ai_text}]")
            history.add_assistant_message(ai_text)
            if agent.name.lower() == 'research':
                logger.debug(f"🔍 Research AI Json {ai_text}")
                report_skill = orchestrator.agent_dir['Report']
                report_response = report_skill.run_report_research_with_ollama(ai_text)
                logger.debug(f"🤖 Report AI Json {report_response}")
                # logger.debug(f"Report AI response {report_response}")
                # ai_json = {'research_result': f"""{report_response}"""}
                ai_json = json.loads(report_response)
                ai_res = ai_json['answer_detail']
                ai_source = json.loads(ai_text)['rag_sources']
            else:  # debug
                ai_json = {'debug_result': f"""{ai_text}"""}
                ai_res = ai_text
                ai_source = None
            # ai_json['agent_assigned'] = agent.name
            # ai_json['agent_assigned_explanation'] = explanation
            # ai_res = json.dumps(ai_json)
            answers.append((ai_res, ai_source))
            logger.info(f"🤖 Agent response: [{ai_res}]")

        except Exception as e:
            logger.error(f"🚨 An error occurred: {e}")
    return answers

# async def answer_question(kernel: Kernel, orchestrator: AgentOrchestrator, questions: list[str]) -> list[str | None]:
#     # Maintain a single ChatHistory object for this session
#     history = ChatHistory()
#     logger.info("🤖 AI new chat created! \n")
#     current_agent_name = None
#     agent, explanation = orchestrator.assign_agent(user_input)
#     if agent is None:
#         no_agent_text = "I can answer technical related question only, please ask another question!"
#         logger.info(no_agent_text)
#         return no_agent_text
#
#     if current_agent_name is None or agent.name != current_agent_name:
#         current_agent_name = agent.name
#         # a new intention, clear old history
#         # and use a new skill to handle
#         history = ChatHistory()
#         history.add_system_message(agent.system_prompt)
#         # logger.debug(f"🤖 (Re)Assign task to agent {agent.name}, system prompt added [ {agent.system_prompt}].")
#         logger.debug(f"🤖 (Re)Assign task to agent {agent.name}")
#
#     if current_agent_name == orchestrator.agent_dir["Research"].name:
#         # grab related information from RAG and third party
#         filtered_user_input = orchestrator.filter_words(user_input)
#
#         logger.debug(f"filtered out user input {filtered_user_input}")
#         rag_search_function = rag_plugin["search_k_content"]
#         rag_result = await kernel.invoke(
#             function=rag_search_function,
#             arguments=KernelArguments(query=filtered_user_input)
#         )
#         # logger.debug(f"☁️ RAG results [{rag_result}]")
#
#         linear_search_function = linear_plugin["search_k_content"]
#         linear_result = await kernel.invoke(
#             function=linear_search_function,
#             arguments=KernelArguments(query=filtered_user_input)
#         )
#         # logger.debug(f"💬 Linear results [{linear_result}]")
#         refined_user_input = construct_user_prompt(str(rag_result),
#                                                    str(linear_result),
#                                                    user_input)
#     else:
#         refined_user_input = user_input.strip()
#     # Append the new user question
#     history.add_user_message(refined_user_input)
#     # logger.debug(f"👩 refined user input: [{refined_user_input}]")
#
#     try:
#         logger.info(f"🤖 Agent: [{agent.name}] thinking...")
#         # logger.debug(f"🤖 Agent: [{agent.name}] thinking with all messages [{history.messages}]...")
#         # Await the response on the STILL-OPEN event loop
#         response = await chat_client.get_chat_message_contents(
#             chat_history=history,
#             settings=settings
#         )
#
#         # Print and save the AI's answer, so it remembers context
#         ai_text = ""
#         for chat_msg in response:
#             chat_text = chat_msg.inner_content.message.content
#             ai_text += chat_text
#
#         # logger.info(f"\nAI: {ai_text}\n")
#         history.add_assistant_message(ai_text)
#         return ai_text
#     except Exception as e:
#         logger.error(f"🚨An error occurred: {e}")


if __name__ == "__main__":
    # Call asyncio.run EXACTLY ONCE here to kick off the whole experience
    asyncio.run(start_chat_session(kernel_instance, orchestrator_instance))
