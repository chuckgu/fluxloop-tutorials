from __future__ import annotations

from datetime import datetime
from typing import Annotated, Iterable, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
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

TUTORIAL_QUESTIONS: List[str] = [
    "Hi there, what time is my flight?",
    "Am i allowed to update my flight to something sooner? I want to leave later today.",
    "Update my flight to sometime next week then",
    "The next available option is great",
    "what about lodging and transportation?",
    "Yeah i think i'd like an affordable hotel for my week-long stay (7 days). And I'll want to rent a car.",
    "OK could you place a reservation for your recommended hotel? It sounds nice.",
    "yes go ahead and book anything that's moderate expense and has availability.",
    "Now for a car, what are my options?",
    "Awesome let's just get the cheapest option. Go ahead and book for 7 days",
    "Cool so now what recommendations do you have on excursions?",
    "Are they available while I'm there?",
    "interesting - i like the museums, what options are there? ",
    "OK great pick one and book it for my second day there.",
]


class State(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]


def build_graph(
    db_path: str,
    *,
    llm: Optional[BaseChatModel] = None,
    extra_tools: Iterable = (),
    checkpointer=None,
):
    """Build the Part 1 zero-shot LangGraph."""
    set_db_path(db_path)

    part_1_tools = [
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
                "\nCurrent time: {time}.",
            ),
            ("placeholder", "{messages}"),
        ]
    ).partial(time=datetime.now)

    runnable = prompt | llm.bind_tools(part_1_tools)

    builder = StateGraph(State)
    builder.add_node("assistant", Assistant(runnable))
    builder.add_node("tools", create_tool_node_with_fallback(part_1_tools))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    memory = checkpointer or InMemorySaver()
    return builder.compile(checkpointer=memory)

