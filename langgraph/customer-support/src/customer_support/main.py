from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable, List, Sequence

import fluxloop
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from customer_support.data.travel_db import (
    DEFAULT_ENV_VAR,
    get_default_storage_dir,
    prepare_database,
)
from customer_support.utils.environment import ensure_env_vars
from customer_support.graphs import (
    PART1_TUTORIAL_QUESTIONS,
    build_part1_graph,
    build_part2_graph,
    build_part3_graph,
    build_part4_graph,
)
from customer_support.utils.console import interactive_turn, run_dialog


GRAPH_BUILDERS = {
    "part1": build_part1_graph,
    "part2": build_part2_graph,
    "part3": build_part3_graph,
    "part4": build_part4_graph,
}

SUPPORTED_PROVIDERS = {"anthropic", "openai"}
DEFAULT_PROVIDER = "anthropic"
PROVIDER_ENV_KEY = "CUSTOMER_SUPPORT_PROVIDER"
OPENAI_MODEL = "gpt-5-mini"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

def resolve_provider(provider: str | None) -> str:
    candidate = (provider or os.environ.get(PROVIDER_ENV_KEY) or DEFAULT_PROVIDER).lower()
    if candidate not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider '{candidate}'. Choose 'anthropic' or 'openai'.")
    return candidate


def required_keys_for(provider: str) -> set[str]:
    keys = {"OPENAI_API_KEY", "TAVILY_API_KEY"}
    if provider == "anthropic":
        keys.add("ANTHROPIC_API_KEY")
    return keys


def prepare_runtime(
    *,
    part: str,
    provider: str | None,
    passenger_id: str,
    data_dir: str | Path | None,
    thread_id: str | None,
    overwrite_db: bool,
    prompt_for_env: bool,
):
    load_dotenv()
    resolved_provider = resolve_provider(provider)
    required_keys = required_keys_for(resolved_provider)
    if prompt_for_env:
        ensure_env_vars(required_keys)

    if data_dir:
        data_dir_path = Path(data_dir).expanduser()
    else:
        data_dir_path = get_default_storage_dir()
    data_dir_path.mkdir(parents=True, exist_ok=True)
    db_path = prepare_database(target_dir=data_dir_path, overwrite=overwrite_db)

    def create_llm():
        if resolved_provider == "openai":
            return ChatOpenAI(model=OPENAI_MODEL, temperature=1)
        return ChatAnthropic(model=ANTHROPIC_MODEL, temperature=1)

    builder = GRAPH_BUILDERS[part]
    graph = builder(str(db_path), llm=create_llm())

    runtime_thread = thread_id or str(uuid.uuid4())
    config = {
        "configurable": {
            "passenger_id": passenger_id,
            "thread_id": runtime_thread,
        }
    }
    return graph, config, resolved_provider


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LangGraph customer support demo from the console."
    )
    parser.add_argument(
        "--part",
        choices=GRAPH_BUILDERS.keys(),
        default="part4",
        help="Which tutorial graph to run.",
    )
    parser.add_argument(
        "--passenger-id",
        default="3442 587242",
        help="Passenger ID used by tools when fetching personalized data.",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Optional thread identifier for LangGraph checkpoints. Defaults to a random UUID.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help=(
            "Directory for storing the travel SQLite database. "
            "Defaults to ~/.cache/customer_support or the "
            f"value of ${DEFAULT_ENV_VAR}."
        ),
    )
    parser.add_argument(
        "--overwrite-db",
        action="store_true",
        help="Force re-download of the SQLite database.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the built-in tutorial question sequence instead of interactive mode.",
    )
    parser.add_argument(
        "--questions-file",
        type=Path,
        help="Optional path to a text file containing questions, one per line, for demo mode.",
    )
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip prompting for missing environment variables (useful in automated environments).",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai"],
        help="LLM provider to use for chat completions (defaults to anthropic or .env override).",
    )
    return parser.parse_args(argv)


def load_questions(questions_file: Path | None) -> List[str]:
    if questions_file:
        return [
            line.strip()
            for line in questions_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return list(PART1_TUTORIAL_QUESTIONS)


def _normalize_prompts(prompts: Iterable[str] | None) -> List[str]:
    if prompts is None:
        return list(PART1_TUTORIAL_QUESTIONS)
    if isinstance(prompts, str):
        text = prompts.strip()
        return [text] if text else list(PART1_TUTORIAL_QUESTIONS)
    normalized: List[str] = []
    for item in prompts:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            normalized.append(text)
    if not normalized:
        return list(PART1_TUTORIAL_QUESTIONS)
    return normalized


def _render_message_content(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts: List[str] = []
        for element in content:
            if isinstance(element, dict):
                text = element.get("text")
                if text:
                    parts.append(text)
            elif element:
                parts.append(str(element))
        content = " ".join(part for part in parts if part).strip()
    if content is None:
        return ""
    return str(content)


def _extract_assistant_text(result: Any) -> str:
    if not isinstance(result, dict):
        return str(result)
    messages = result.get("messages")
    if not messages:
        return ""
    if isinstance(messages, list):
        message = messages[-1]
    else:
        message = messages
    return _render_message_content(message)


@fluxloop.agent(name="customer_support_session")
def run_customer_support_session(
    prompts: Iterable[str] | None = None,
    *,
    part: str = "part4",
    provider: str | None = None,
    passenger_id: str = "3442 587242",
    thread_id: str | None = None,
    data_dir: str | None = None,
    overwrite_db: bool = False,
    prompt_for_env: bool = False,
) -> dict[str, Any]:
    graph, config, resolved_provider = prepare_runtime(
        part=part,
        provider=provider,
        passenger_id=passenger_id,
        data_dir=data_dir,
        thread_id=thread_id,
        overwrite_db=overwrite_db,
        prompt_for_env=prompt_for_env,
    )
    questions = _normalize_prompts(prompts)
    transcript = []
    for text in questions:
        turn = {"user": text}
        result = graph.invoke({"messages": ("user", text)}, config)
        turn["assistant"] = _extract_assistant_text(result)
        transcript.append(turn)
    return {
        "transcript": transcript,
        "thread_id": config["configurable"]["thread_id"],
        "provider": resolved_provider,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    graph, config, _ = prepare_runtime(
        part=args.part,
        provider=args.provider,
        passenger_id=args.passenger_id,
        data_dir=args.data_dir,
        thread_id=args.thread_id,
        overwrite_db=args.overwrite_db,
        prompt_for_env=not args.skip_env,
    )

    if args.demo:
        questions = load_questions(args.questions_file)
        run_dialog(graph, questions, config)
        return 0

    print(
        "Interactive mode. Type your question and press enter. "
        "Submit an empty line (or Ctrl-D) to exit."
    )
    printed_set = set()
    while True:
        try:
            text = input("You: ").strip()
        except EOFError:
            print()
            break
        if not text:
            break
        interactive_turn(
            graph,
            {"messages": ("user", text)},
            config,
            printed_set,
        )
    print("Goodbye!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

