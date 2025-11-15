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
    extra_tools: Iterable = (),
    checkpointer=None,
):
    """Build the Part 2 graph with tool confirmation interrupts."""
    set_db_path(db_path)

    tools = [
        TavilySearchResults(max_results=1),
        fetch_user_flight_information,
        search_flights,
        lookup_policy,
        update_ticket_to_new_flight,
        cancel_ticket,
        search_car_rentals,
        book_car_rental,
        update_car_rental,
        cancel_car_rental,
        search_hotels,
        book_hotel,
        update_hotel,
        cancel_hotel,
        search_trip_recommendations,
        book_excursion,
        update_excursion,
        cancel_excursion,
        *extra_tools,
    ]

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

    runnable = prompt | llm.bind_tools(tools)

    def fetch_user_info(state, config):
        try:
            user_info = fetch_user_flight_information.invoke({}, config=config)
        except Exception:
            user_info = []
        return {"user_info": user_info}

    builder = StateGraph(State)
    builder.add_node("fetch_user_info", RunnableLambda(fetch_user_info))
    builder.add_node("assistant", Assistant(runnable))
    builder.add_node("tools", create_tool_node_with_fallback(tools))
    builder.add_edge(START, "fetch_user_info")
    builder.add_edge("fetch_user_info", "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    memory = checkpointer or InMemorySaver()
    return builder.compile(
        checkpointer=memory,
        interrupt_before=["tools"],
    )

