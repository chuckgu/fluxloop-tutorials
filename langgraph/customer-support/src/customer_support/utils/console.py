from __future__ import annotations

from typing import Any, Dict, Iterable, Set

from langchain_core.messages import ToolMessage

from .langgraph import print_event


APPROVAL_PROMPT = (
    "Do you approve of the above actions? Type 'y' to continue; "
    "otherwise, explain the requested change.\n\n"
)


def stream_events(graph, payload, config, printed: Set[str]) -> None:
    events = graph.stream(payload, config, stream_mode="values")
    for event in events:
        print_event(event, printed)


def handle_interrupts(graph, config, printed: Set[str], prompt: str = APPROVAL_PROMPT):
    snapshot = graph.get_state(config)
    while snapshot.next:
        ai_message = snapshot.values["messages"][-1]
        tool_calls = getattr(ai_message, "tool_calls", None)
        if not tool_calls:
            break
        try:
            user_input = input(prompt)
        except EOFError:
            user_input = "y"
        if user_input.strip().lower() in {"y", "yes", ""}:
            payload = None
        else:
            payload = {
                "messages": [
                    ToolMessage(
                        tool_call_id=tool_calls[0]["id"],
                        content=(
                            "API call denied by user. "
                            f"Reasoning: '{user_input}'. Continue assisting, accounting for the user's input."
                        ),
                    )
                ]
            }
        stream_events(graph, payload, config, printed)
        snapshot = graph.get_state(config)


def interactive_turn(
    graph,
    message: Dict[str, Any],
    config: Dict[str, Any],
    printed: Set[str],
    *,
    approval_prompt: str = APPROVAL_PROMPT,
) -> None:
    stream_events(graph, message, config, printed)
    handle_interrupts(graph, config, printed, approval_prompt)


def run_dialog(
    graph,
    messages: Iterable[str],
    config: Dict[str, Any],
    *,
    approval_prompt: str = APPROVAL_PROMPT,
) -> None:
    printed: Set[str] = set()
    for text in messages:
        print(f"\n=== User ===\n{text}")
        interactive_turn(
            graph,
            {"messages": ("user", text)},
            config,
            printed,
            approval_prompt=approval_prompt,
        )

