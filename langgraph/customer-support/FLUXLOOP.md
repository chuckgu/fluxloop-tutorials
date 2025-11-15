# FluxLoop Integration Guide

This guide explains how to run the LangGraph customer support tutorial with FluxLoop for reproducible simulations, evaluation, and tooling support. It builds on the official FluxLoop documentation, so keep the primary docs handy while following along ([FluxLoop overview](https://fluxloop.io/docs), [FluxLoop SDK](https://fluxloop.io/sdk)).

## Prerequisites

- Python 3.11+
- Installed dependencies (handled by `uv sync`):

  ```bash
  uv sync
  ```

- FluxLoop tooling (SDK, CLI, and MCP server) installed in your active environment:

  ```bash
  pip install fluxloop fluxloop-cli fluxloop-mcp
  ```

  Refer to the official installation instructions for platform-specific details ([FluxLoop SDK](https://fluxloop.io/sdk), [CLI quick start](https://fluxloop.io/docs), [MCP server setup](https://fluxloop.io/mcp/installation)).

- API keys for Anthropic/OpenAI/Tavily placed in `.env` or exported before execution.

## Instrumentation Summary

FluxLoop tracing is wired directly into the LangGraph project:

- The session runner is decorated with `@fluxloop.agent`, making every conversation callable from FluxLoop CLI or other runners.

```217:249:langgraph/customer-support/src/customer_support/main.py
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
```

- All LangChain tool functions are wrapped with `@fluxloop.trace`, so database reads, writes, and policy lookups show up in FluxLoop traces.

```12:35:langgraph/customer-support/src/customer_support/tools/cars.py
@tool
@fluxloop.trace(name="search_car_rentals")
def search_car_rentals(...):
    ...
```

The same pattern is applied across flights, hotels, excursions, policies, and database utilities, ensuring consistent observability throughout the tutorial.

## Local Dry Runs (without FluxLoop CLI)

You can continue to launch the built-in console driver:

```bash
uv run python -m customer_support.main --demo          # scripted walk-through
uv run python -m customer_support.main                 # interactive CLI
uv run python -m customer_support.main --part part2    # select a specific stage
```

These commands now produce FluxLoop traces for each assistant and tool call.

## FluxLoop CLI Runner Configuration

Create `configs/simulation.yaml` in the project root to point FluxLoop at the new session runner. The simplest configuration uses the “Python function” runner ([runner targets reference](https://fluxloop.io/cli/configuration/runner-targets)):

```yaml
runner:
  target: "customer_support.main:run_customer_support_session"
  working_directory: .
  python_path: ["src"]
  args:
    part: part4
    provider: anthropic
    prompt_for_env: false

inputs:
  dataset: inputs/tutorial_prompts.jsonl  # generated via fluxloop CLI
```

Pick or generate an input dataset with the standard CLI workflow:

```bash
fluxloop generate inputs --limit 25
fluxloop run experiment
```

FluxLoop will stream trace artifacts (JSONL) into the `experiments/` directory, including tool-level observations captured by the `@fluxloop.trace` decorators ([FluxLoop CLI quick start](https://fluxloop.io/docs)).

## Optional: MCP Server for IDE Guidance

Installing the FluxLoop MCP server enables Cursor/VS Code to surface integration recipes and troubleshooting tips directly inside the editor ([FluxLoop MCP installation](https://fluxloop.io/mcp/installation)). Once installed, point Cursor’s MCP configuration at the `fluxloop-mcp` binary and restart the client to fetch LangGraph-specific suggestions.

## Next Steps

- Extend the tutorial with additional prompts or LangGraph variants—FluxLoop automatically records the new branches.
- Experiment with alternative runner targets (REST/SSE, subprocess) if you containerize or remote-host the agent ([runner targets reference](https://fluxloop.io/cli/configuration/runner-targets)).
- Explore FluxLoop’s evaluation tooling by defining rule-based or LLM-based evaluators to score the transcripts after each experiment run.

With these hooks in place you can iterate locally, run scripted experiments, or wire the project into larger agent evaluation pipelines with full observability. Happy testing!

