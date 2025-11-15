from __future__ import annotations

from datetime import datetime
from typing import Annotated, Callable, List, Literal, Optional

from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableConfig
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field
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


def update_dialog_stack(left: List[str], right: Optional[str]) -> List[str]:
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]


class State(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    user_info: List[dict]
    dialog_state: Annotated[
        List[
            Literal[
                "primary_assistant",
                "update_flight",
                "book_car_rental",
                "book_hotel",
                "book_excursion",
            ]
        ],
        update_dialog_stack,
    ]


class CompleteOrEscalate(BaseModel):
    """Mark the delegated workflow as completed or escalate back to the primary assistant."""

    cancel: bool = True
    reason: str


class ToFlightBookingAssistant(BaseModel):
    """Transfers work to the flight update assistant."""

    request: str = Field(
        description="Follow-up questions or key details the flight assistant should know."
    )


class ToBookCarRental(BaseModel):
    """Transfers work to the car rental assistant."""

    location: str
    start_date: str
    end_date: str
    request: str


class ToHotelBookingAssistant(BaseModel):
    """Transfers work to the hotel booking assistant."""

    location: str
    checkin_date: str
    checkout_date: str
    request: str


class ToBookExcursion(BaseModel):
    """Transfers work to the excursion assistant."""

    location: str
    request: str


def _build_assistant_prompt(system_template: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_template),
            ("placeholder", "{messages}"),
        ]
    ).partial(time=datetime.now)


def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: State) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=(
                        f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                        f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                        " and the booking, update, or other action is not complete until after you have successfully invoked the appropriate tool."
                        " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                        " Do not mention who you are - just act as the proxy for the assistant."
                    ),
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }

    return entry_node


def pop_dialog_state(state: State) -> dict:
    messages = []
    ai_message = state["messages"][-1]
    if ai_message.tool_calls:
        messages.append(
            ToolMessage(
                content=(
                    "Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed."
                ),
                tool_call_id=ai_message.tool_calls[0]["id"],
            )
        )
    return {"dialog_state": "pop", "messages": messages}


def build_graph(
    db_path: str,
    *,
    llm: Optional[BaseChatModel] = None,
    checkpointer=None,
):
    """Build the Part 4 specialized workflow graph."""
    set_db_path(db_path)

    if llm is None:
        llm = ChatAnthropic(model=DEFAULT_MODEL, temperature=1)

    flight_prompt = _build_assistant_prompt(
        "You are a specialized assistant for handling flight updates. "
        "The primary assistant delegates work to you whenever the user needs help updating their bookings. "
        "Confirm the updated flight details with the customer and inform them of any additional fees. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
        "Remember that a booking isn't completed until after the relevant tool has successfully been used."
        "\n\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
        "\nCurrent time: {time}."
        '\n\nIf the user needs help, and none of your tools are appropriate for it, then "CompleteOrEscalate" the dialog to the host assistant.'
        " Do not waste the user's time. Do not make up invalid tools or functions."
    )
    update_flight_safe_tools = [search_flights]
    update_flight_sensitive_tools = [update_ticket_to_new_flight, cancel_ticket]
    update_flight_runnable = flight_prompt | llm.bind_tools(
        update_flight_safe_tools + update_flight_sensitive_tools + [CompleteOrEscalate]
    )

    hotel_prompt = _build_assistant_prompt(
        "You are a specialized assistant for handling hotel bookings. "
        "The primary assistant delegates work to you whenever the user needs help booking a hotel. "
        "Search for available hotels based on the user's preferences and confirm the booking details with the customer. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
        "Remember that a booking isn't completed until after the relevant tool has successfully been used."
        "\nCurrent time: {time}."
        '\n\nIf the user needs help, and none of your tools are appropriate for it, then "CompleteOrEscalate" the dialog to the host assistant.'
        " Do not waste the user's time. Do not make up invalid tools or functions."
    )
    book_hotel_safe_tools = [search_hotels]
    book_hotel_sensitive_tools = [book_hotel, update_hotel, cancel_hotel]
    book_hotel_runnable = hotel_prompt | llm.bind_tools(
        book_hotel_safe_tools + book_hotel_sensitive_tools + [CompleteOrEscalate]
    )

    car_prompt = _build_assistant_prompt(
        "You are a specialized assistant for handling car rental bookings. "
        "The primary assistant delegates work to you whenever the user needs help booking a car rental. "
        "Search for available car rentals based on the user's preferences and confirm the booking details with the customer. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
        "Remember that a booking isn't completed until after the relevant tool has successfully been used."
        "\nCurrent time: {time}."
        '\n\nIf the user needs help, and none of your tools are appropriate for it, then "CompleteOrEscalate" the dialog to the host assistant.'
        " Do not waste the user's time. Do not make up invalid tools or functions."
    )
    book_car_rental_safe_tools = [search_car_rentals]
    book_car_rental_sensitive_tools = [
        book_car_rental,
        update_car_rental,
        cancel_car_rental,
    ]
    book_car_rental_runnable = car_prompt | llm.bind_tools(
        book_car_rental_safe_tools + book_car_rental_sensitive_tools + [CompleteOrEscalate]
    )

    excursion_prompt = _build_assistant_prompt(
        "You are a specialized assistant for handling trip recommendations. "
        "The primary assistant delegates work to you whenever the user needs help booking a recommended trip. "
        "Search for available trip recommendations based on the user's preferences and confirm the booking details with the customer. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
        "Remember that a booking isn't completed until after the relevant tool has successfully been used."
        "\nCurrent time: {time}."
        '\n\nIf the user needs help, and none of your tools are appropriate for it, then "CompleteOrEscalate" the dialog to the host assistant.'
        " Do not waste the user's time. Do not make up invalid tools or functions."
    )
    book_excursion_safe_tools = [search_trip_recommendations]
    book_excursion_sensitive_tools = [book_excursion, update_excursion, cancel_excursion]
    book_excursion_runnable = excursion_prompt | llm.bind_tools(
        book_excursion_safe_tools + book_excursion_sensitive_tools + [CompleteOrEscalate]
    )

    primary_prompt = _build_assistant_prompt(
        "You are a helpful customer support assistant for Swiss Airlines. "
        "Your primary role is to search for flight information and company policies to answer customer queries. "
        "If a customer requests to update or cancel a flight, book a car rental, book a hotel, or get trip recommendations, "
        "delegate the task to the appropriate specialized assistant by invoking the corresponding tool. You are not able to make these types of changes yourself."
        "Only the specialized assistants are given permission to do this for the user."
        "The user is not aware of the different specialized assistants, so do not mention them; just quietly delegate through function calls. "
        "Provide detailed information to the customer, and always double-check the database before concluding that information is unavailable. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "If a search comes up empty, expand your search before giving up."
        "\n\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
        "\nCurrent time: {time}."
    )
    primary_safe_tools = [
        TavilySearchResults(max_results=1),
        search_flights,
        lookup_policy,
    ]
    primary_binding_tools = primary_safe_tools + [
        ToFlightBookingAssistant,
        ToBookCarRental,
        ToHotelBookingAssistant,
        ToBookExcursion,
    ]
    primary_runnable = primary_prompt | llm.bind_tools(primary_binding_tools)

    builder = StateGraph(State)

    def fetch_user_info(state: State, config: RunnableConfig):
        try:
            user_info = fetch_user_flight_information.invoke({}, config=config)
        except Exception:
            user_info = []
        return {"user_info": user_info, "dialog_state": ["primary_assistant"]}

    builder.add_node("fetch_user_info", RunnableLambda(fetch_user_info))
    builder.add_edge(START, "fetch_user_info")

    builder.add_node(
        "enter_update_flight",
        create_entry_node("Flight Updates & Booking Assistant", "update_flight"),
    )
    builder.add_node("update_flight", Assistant(update_flight_runnable))
    builder.add_edge("enter_update_flight", "update_flight")
    builder.add_node(
        "update_flight_safe_tools",
        create_tool_node_with_fallback(update_flight_safe_tools),
    )
    builder.add_node(
        "update_flight_sensitive_tools",
        create_tool_node_with_fallback(update_flight_sensitive_tools),
    )

    def route_update_flight(state: State):
        next_node = tools_condition(state)
        if next_node == END:
            return END
        tool_calls = state["messages"][-1].tool_calls
        if any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls):
            return "leave_skill"
        safe_names = {tool.name for tool in update_flight_safe_tools}
        if all(tc["name"] in safe_names for tc in tool_calls):
            return "update_flight_safe_tools"
        return "update_flight_sensitive_tools"

    builder.add_edge("update_flight_safe_tools", "update_flight")
    builder.add_edge("update_flight_sensitive_tools", "update_flight")
    builder.add_conditional_edges(
        "update_flight",
        route_update_flight,
        ["update_flight_safe_tools", "update_flight_sensitive_tools", "leave_skill", END],
    )

    builder.add_node(
        "enter_book_car_rental",
        create_entry_node("Car Rental Assistant", "book_car_rental"),
    )
    builder.add_node("book_car_rental", Assistant(book_car_rental_runnable))
    builder.add_edge("enter_book_car_rental", "book_car_rental")
    builder.add_node(
        "book_car_rental_safe_tools",
        create_tool_node_with_fallback(book_car_rental_safe_tools),
    )
    builder.add_node(
        "book_car_rental_sensitive_tools",
        create_tool_node_with_fallback(book_car_rental_sensitive_tools),
    )

    def route_book_car_rental(state: State):
        next_node = tools_condition(state)
        if next_node == END:
            return END
        tool_calls = state["messages"][-1].tool_calls
        if any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls):
            return "leave_skill"
        safe_names = {tool.name for tool in book_car_rental_safe_tools}
        if all(tc["name"] in safe_names for tc in tool_calls):
            return "book_car_rental_safe_tools"
        return "book_car_rental_sensitive_tools"

    builder.add_edge("book_car_rental_safe_tools", "book_car_rental")
    builder.add_edge("book_car_rental_sensitive_tools", "book_car_rental")
    builder.add_conditional_edges(
        "book_car_rental",
        route_book_car_rental,
        [
            "book_car_rental_safe_tools",
            "book_car_rental_sensitive_tools",
            "leave_skill",
            END,
        ],
    )

    builder.add_node(
        "enter_book_hotel",
        create_entry_node("Hotel Booking Assistant", "book_hotel"),
    )
    builder.add_node("book_hotel", Assistant(book_hotel_runnable))
    builder.add_edge("enter_book_hotel", "book_hotel")
    builder.add_node(
        "book_hotel_safe_tools",
        create_tool_node_with_fallback(book_hotel_safe_tools),
    )
    builder.add_node(
        "book_hotel_sensitive_tools",
        create_tool_node_with_fallback(book_hotel_sensitive_tools),
    )

    def route_book_hotel(state: State):
        next_node = tools_condition(state)
        if next_node == END:
            return END
        tool_calls = state["messages"][-1].tool_calls
        if any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls):
            return "leave_skill"
        safe_names = {tool.name for tool in book_hotel_safe_tools}
        if all(tc["name"] in safe_names for tc in tool_calls):
            return "book_hotel_safe_tools"
        return "book_hotel_sensitive_tools"

    builder.add_edge("book_hotel_safe_tools", "book_hotel")
    builder.add_edge("book_hotel_sensitive_tools", "book_hotel")
    builder.add_conditional_edges(
        "book_hotel",
        route_book_hotel,
        ["book_hotel_safe_tools", "book_hotel_sensitive_tools", "leave_skill", END],
    )

    builder.add_node(
        "enter_book_excursion",
        create_entry_node("Trip Recommendation Assistant", "book_excursion"),
    )
    builder.add_node("book_excursion", Assistant(book_excursion_runnable))
    builder.add_edge("enter_book_excursion", "book_excursion")
    builder.add_node(
        "book_excursion_safe_tools",
        create_tool_node_with_fallback(book_excursion_safe_tools),
    )
    builder.add_node(
        "book_excursion_sensitive_tools",
        create_tool_node_with_fallback(book_excursion_sensitive_tools),
    )

    def route_book_excursion(state: State):
        next_node = tools_condition(state)
        if next_node == END:
            return END
        tool_calls = state["messages"][-1].tool_calls
        if any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls):
            return "leave_skill"
        safe_names = {tool.name for tool in book_excursion_safe_tools}
        if all(tc["name"] in safe_names for tc in tool_calls):
            return "book_excursion_safe_tools"
        return "book_excursion_sensitive_tools"

    builder.add_edge("book_excursion_safe_tools", "book_excursion")
    builder.add_edge("book_excursion_sensitive_tools", "book_excursion")
    builder.add_conditional_edges(
        "book_excursion",
        route_book_excursion,
        ["book_excursion_safe_tools", "book_excursion_sensitive_tools", "leave_skill", END],
    )

    builder.add_node("primary_assistant", Assistant(primary_runnable))
    builder.add_node(
        "primary_assistant_tools",
        create_tool_node_with_fallback(primary_safe_tools),
    )

    def route_primary_assistant(state: State):
        next_node = tools_condition(state)
        if next_node == END:
            return END
        tool_calls = state["messages"][-1].tool_calls
        if not tool_calls:
            return "primary_assistant_tools"
        first_call = tool_calls[0]["name"]
        if first_call == ToFlightBookingAssistant.__name__:
            return "enter_update_flight"
        if first_call == ToBookCarRental.__name__:
            return "enter_book_car_rental"
        if first_call == ToHotelBookingAssistant.__name__:
            return "enter_book_hotel"
        if first_call == ToBookExcursion.__name__:
            return "enter_book_excursion"
        return "primary_assistant_tools"

    builder.add_conditional_edges(
        "primary_assistant",
        route_primary_assistant,
        [
            "enter_update_flight",
            "enter_book_car_rental",
            "enter_book_hotel",
            "enter_book_excursion",
            "primary_assistant_tools",
            END,
        ],
    )
    builder.add_edge("primary_assistant_tools", "primary_assistant")

    builder.add_node("leave_skill", pop_dialog_state)
    builder.add_edge("leave_skill", "primary_assistant")

    def route_to_workflow(
        state: State,
    ) -> Literal[
        "primary_assistant",
        "update_flight",
        "book_car_rental",
        "book_hotel",
        "book_excursion",
    ]:
        dialog_state = state.get("dialog_state", [])
        if not dialog_state:
            return "primary_assistant"
        return dialog_state[-1]

    builder.add_conditional_edges(
        "fetch_user_info",
        route_to_workflow,
        [
            "primary_assistant",
            "update_flight",
            "book_car_rental",
            "book_hotel",
            "book_excursion",
        ],
    )

    memory = checkpointer or InMemorySaver()
    return builder.compile(
        checkpointer=memory,
        interrupt_before=[
            "update_flight_sensitive_tools",
            "book_car_rental_sensitive_tools",
            "book_hotel_sensitive_tools",
            "book_excursion_sensitive_tools",
        ],
    )

