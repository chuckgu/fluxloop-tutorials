from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Iterable, List, Sequence

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from customer_support import ensure_env_vars, prepare_database
from customer_support.data.travel_db import get_default_storage_dir, DEFAULT_ENV_VAR
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

DEFAULT_PROVIDER = "anthropic"
PROVIDER_ENV_KEY = "CUSTOMER_SUPPORT_PROVIDER"
OPENAI_MODEL = "gpt-5-mini"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


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


def load_questions(args: argparse.Namespace) -> Iterable[str]:
    if args.questions_file:
        return [
            line.strip()
            for line in args.questions_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return PART1_TUTORIAL_QUESTIONS


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    load_dotenv()

    provider = (args.provider or os.environ.get(PROVIDER_ENV_KEY) or DEFAULT_PROVIDER).lower()
    if provider not in {"anthropic", "openai"}:
        raise ValueError(f"Unsupported provider '{provider}'. Choose 'anthropic' or 'openai'.")

    required_keys = {"OPENAI_API_KEY", "TAVILY_API_KEY"}
    if provider == "anthropic":
        required_keys.add("ANTHROPIC_API_KEY")

    if not args.skip_env:
        ensure_env_vars(required_keys)

    if args.data_dir:
        data_dir = Path(args.data_dir).expanduser()
    else:
        data_dir = get_default_storage_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = prepare_database(target_dir=data_dir, overwrite=args.overwrite_db)

    def create_llm():
        if provider == "openai":
            return ChatOpenAI(model=OPENAI_MODEL, temperature=1)
        return ChatAnthropic(model=ANTHROPIC_MODEL, temperature=1)

    builder = GRAPH_BUILDERS[args.part]
    graph = builder(str(db_path), llm=create_llm())

    thread_id = args.thread_id or str(uuid.uuid4())
    config = {
        "configurable": {
            "passenger_id": args.passenger_id,
            "thread_id": thread_id,
        }
    }

    if args.demo:
        questions = list(load_questions(args))
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

