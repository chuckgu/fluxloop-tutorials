from __future__ import annotations

from typing import Any, Dict

import fluxloop

from langchain_core.runnables import Runnable, RunnableConfig


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    @fluxloop.trace(name="assistant_turn")
    def __call__(self, state: Dict[str, Any], config: RunnableConfig):
        current_state = dict(state)
        while True:
            result = self.runnable.invoke(current_state)
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = current_state["messages"] + [
                    ("user", "Respond with a real output.")
                ]
                current_state = {**current_state, "messages": messages}
                continue
            break
        return {"messages": result}

