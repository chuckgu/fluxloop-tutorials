from __future__ import annotations

from datetime import datetime
from typing import Annotated, Iterable, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.language_models.chat_models import BaseChatModel
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import tools_condition

from customer_support.assistant import Assistant
from customer_support.tools import (
    book_car_rental,
    book_excursion,
    book_hotel,
    cancel_car_rental,
    cancel_excursion,
    cancel_hotel,
    cancel_ticket,
    fetch_user_flight_information,
    lookup_policy,
    search_car_rentals,
    search_flights,
    search_hotels,
    search_trip_recommendations,
    update_car_rental,
    update_excursion,
    update_hotel,
    update_ticket_to_new_flight,
    set_db_path,
)
from customer_support.utils.langgraph import create_tool_node_with_fallback

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class State(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    user_info: List[dict]


def build_graph(
    db_path: str,
    *,
    llm: Optional[BaseChatModel] = None,
    extra_safe_tools: Iterable = (),
    extra_sensitive_tools: Iterable = (),
    checkpointer=None,
):
    """Build the Part 3 graph with conditional interrupts."""
    set_db_path(db_path)

    safe_tools = [
        TavilySearchResults(max_results=1),
        fetch_user_flight_information,
        search_flights,
        lookup_policy,
        search_car_rentals,
        search_hotels,
        search_trip_recommendations,
        *extra_safe_tools,
    ]
    sensitive_tools = [
        update_ticket_to_new_flight,
        cancel_ticket,
        book_car_rental,
        update_car_rental,
        cancel_car_rental,
        book_hotel,
        update_hotel,
        cancel_hotel,
        book_excursion,
        update_excursion,
        cancel_excursion,
        *extra_sensitive_tools,
    ]
    sensitive_tool_names = {tool.name for tool in sensitive_tools}
    safe_tool_names = {tool.name for tool in safe_tools}

    if llm is None:
        llm = ChatAnthropic(model=DEFAULT_MODEL, temperature=1)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful customer support assistant for Swiss Airlines. "
                "Use the provided tools to search for flights, company policies, and other information to assist the user's queries. "
                "When searching, be persistent. Expand your query bounds if the first search returns no results. "
                "If a search comes up empty, expand your search before giving up."
                "\n\nCurrent user:\n<User>\n{user_info}\n</User>"
                "\nCurrent time: {time}.",
            ),
            ("placeholder", "{messages}"),
        ]
    ).partial(time=datetime.now)

    runnable = prompt | llm.bind_tools(safe_tools + sensitive_tools)

    def fetch_user_info(state, config):
        try:
            user_info = fetch_user_flight_information.invoke({}, config=config)
        except Exception:
            user_info = []
        return {"user_info": user_info}

    builder = StateGraph(State)
    builder.add_node("fetch_user_info", RunnableLambda(fetch_user_info))
    builder.add_node("assistant", Assistant(runnable))
    builder.add_node("safe_tools", create_tool_node_with_fallback(safe_tools))
    builder.add_node("sensitive_tools", create_tool_node_with_fallback(sensitive_tools))
    builder.add_edge(START, "fetch_user_info")
    builder.add_edge("fetch_user_info", "assistant")

    def route_tools(state: State):
        next_node = tools_condition(state)
        if next_node == END:
            return END
        ai_message = state["messages"][-1]
        if not ai_message.tool_calls:
            return END
        first_tool_call = ai_message.tool_calls[0]
        tool_name = first_tool_call["name"]
        if tool_name in sensitive_tool_names:
            return "sensitive_tools"
        if tool_name in safe_tool_names:
            return "safe_tools"
        # default to safe tools if unknown
        return "safe_tools"

    builder.add_conditional_edges(
        "assistant",
        route_tools,
        ["safe_tools", "sensitive_tools", END],
    )
    builder.add_edge("safe_tools", "assistant")
    builder.add_edge("sensitive_tools", "assistant")

    memory = checkpointer or InMemorySaver()
    return builder.compile(
        checkpointer=memory,
        interrupt_before=["sensitive_tools"],
    )

