# Customer Support LangGraph Conversion

Console-friendly port of the LangGraph “customer support” tutorial notebook.  
Includes the four tutorial graph variants, SQLite setup utilities, and a CLI runner.

## Quick start

1. Install Python dependencies:

   ```bash
   uv sync
   ```

2. Provide API keys. Keys placed in a local `.env` file are loaded automatically, or export them manually:

   ```bash
   export ANTHROPIC_API_KEY=...
   export OPENAI_API_KEY=...
   export TAVILY_API_KEY=...
   export CUSTOMER_SUPPORT_PROVIDER=anthropic  # optional fallback, see below
   ```

3. Run the CLI (defaults to Part 4 graph):

   ```bash
   uv run python -m customer_support.main --demo
   ```

   Use `--part part1|part2|part3|part4` to choose a tutorial stage.

## API keys

Set `OPENAI_API_KEY` (used for embeddings), `TAVILY_API_KEY`, and—when using Anthropic—`ANTHROPIC_API_KEY`.
Missing keys trigger an interactive prompt unless `--skip-env` is used.

`.env` example:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-openai-...
TAVILY_API_KEY=tvly-...
CUSTOMER_SUPPORT_PROVIDER=anthropic   # or openai
```

Copy & paste template (fill in your keys before saving as `.env`):

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
TAVILY_API_KEY=
CUSTOMER_SUPPORT_PROVIDER=anthropic
```

## Data storage

- SQLite databases are stored at `~/.cache/customer_support` by default.
- Override with the `CUSTOMER_SUPPORT_DATA_DIR` environment variable or `--data-dir` CLI flag.
- The directory is created automatically if it does not exist.

## CLI options

- `--part`: select which graph implementation to run.
- `--provider`: choose `anthropic` (default) or `openai`/`gpt-5-mini` for the primary LLM.
- `--demo`: stream the canonical tutorial conversation.
- `--questions-file`: feed custom demo prompts.
- `--data-dir`: pick where the travel SQLite DB is stored (defaults to `~/.cache/customer_support` or `CUSTOMER_SUPPORT_DATA_DIR`).
- `--overwrite-db`: force re-download/reset of the SQLite DB.
- `--passenger-id`, `--thread-id`: override defaults for tool config/checkpointing.
- `--skip-env`: run without environment-variable prompts (assume they are preset).

CLI respects the `CUSTOMER_SUPPORT_PROVIDER` env var when `--provider` is omitted.

## Project layout

- `src/customer_support/data/`: travel database bootstrap utilities.
- `src/customer_support/tools/`: policy retrieval and booking tools.
- `src/customer_support/graphs/`: Part 1–4 graph builders.
- `src/customer_support/utils/`: shared helpers (LangGraph fallbacks, console driver).
- `src/customer_support/main.py`: CLI entry point.

