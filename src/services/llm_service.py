from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from typing import TypedDict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from src.core.config import get_settings
from src.core.logging import get_logger
from src.utils.prompts import SYSTEM_PROMPT, build_user_message
from src.utils.db import execute_query

logger = get_logger(__name__)
settings = get_settings()

llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model=settings.MODEL_NAME,
    temperature=0
)

# ——— LangGraph State ———
class AgentState(TypedDict):
    question: str
    sql: str
    result: list[dict[str, Any]]
    error: str | None


# ——— GraphNodes ———
def generate_sql(state: AgentState) -> AgentState:
    logger.info(f"Generating SQL for {state["question"]}")
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=build_user_message(state["question"]))
    ]
    if state["error"]:
        messages.append(HumanMessage(
            content=f"The previous SQL failed with error: {state['error']}\n"
                    f"Previous SQL: {state['sql']}\n"
                    f"Please fix it and return only the corrected SQL."
        ))
    response = llm.invoke(messages)
    sql = response.content.strip().strip("```sql").strip("```").strip()
    logger.info(f"Generated SQL: {sql}")
    return {**state, "sql": sql, "error": None}

def execute_sql(state: AgentState) -> AgentState:
    try:
        result = execute_query(state["sql"])
        return {**state, "result": result, "error": None}
    except Exception as e:
        logger.warning(f"SQL execution failed: {e}")
        return {**state, "result": [], "error": str(e)}

# def generate_sql(state: AgentState) -> AgentState:
#     ...

# ——— Build Graph ———
def _build_graph() -> Any:
    graph = StateGraph(AgentState)

    graph.add_node("generate_sql", generate_sql)
    graph.add_node("execute_sql", execute_sql)

    graph.set_entry_point("generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    # graph.add_conditional_edges(
    #     "execute_sql",
    #     should_retry,
    #     {"retry": "generate_sql", "done": END}
    # )
    return graph.compile()

agent = _build_graph()
def run_agent(question: str) -> dict[str, Any]:
    initial_state: AgentState = {
        "question": question,
        "sql": "",
        "result": [],
        "error": None,

    }
    final_state = agent.invoke(initial_state)
    return {
        "sql": final_state["sql"],
        "result": final_state["result"],
        "error": final_state["error"]
    }


if __name__ == "__main__":
    question = "show revenue by region for 2025-09-01"
    print(run_agent(question))