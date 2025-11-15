# FluxLoop Tutorials

A collection of AI agent tutorials demonstrating integration with [FluxLoop](https://github.com/chuckgu/fluxloop) for simulation, evaluation, and testing.

## About FluxLoop

**FluxLoop** is an open-source toolkit for running reproducible, offline-first simulations of AI agents against dynamic scenarios. It empowers developers to rigorously test agent behavior, evaluate performance against custom criteria, and build confidence before shipping to production.

### Key Features

- 🎯 **Simple Decorator-Based Instrumentation**: Add `@fluxloop.agent()` to trace agent execution
- 🧪 **Offline-First Simulation**: Run experiments locally with full control and reproducibility
- 📊 **Evaluation-First Testing**: Define custom evaluators and success criteria
- 🔌 **Framework-Agnostic**: Works with LangGraph, LangChain, and custom agent frameworks

Visit the [FluxLoop repository](https://github.com/chuckgu/fluxloop) for installation and documentation.

---

## Purpose of This Repository

This repository provides **ready-to-run AI agent examples** that can be used for:

1. **Learning**: Understand how to build agents with popular frameworks
2. **FluxLoop Integration**: See practical examples of instrumenting agents with FluxLoop decorators
3. **Testing & Evaluation**: Use as baseline implementations for your own simulations
4. **Benchmarking**: Compare different agent architectures and approaches

Each tutorial is a self-contained project with:
- Complete source code
- Setup instructions
- CLI interface for easy testing
- FluxLoop instrumentation examples (where applicable)

---

## Available Tutorials

### LangGraph

#### 📞 [Customer Support Agent](./langgraph/customer-support/)

A console-friendly port of the official LangGraph customer support tutorial. Demonstrates a multi-stage agentic system with tool calling, memory, and human-in-the-loop workflows.

**What You'll Learn:**
- Building stateful agents with LangGraph
- Implementing tool calling for database queries and bookings
- Managing conversation state and checkpointing
- Progressive complexity across 4 tutorial stages

**Features:**
- 🛠️ Booking tools for flights, hotels, car rentals, and excursions
- 💾 SQLite database integration with travel data
- 🔄 Four progressive graph implementations (Part 1-4)
- 🎨 Rich console UI with streaming responses
- ⚙️ Configurable LLM provider (Anthropic/OpenAI)

**Quick Start:**
```bash
cd langgraph/customer-support
uv sync
uv run python -m customer_support.main --demo
```

See the [customer-support README](./langgraph/customer-support/README.md) for detailed setup and usage.

---

## Integrating with FluxLoop

All tutorials in this repository are designed to work seamlessly with FluxLoop. Here's how to instrument and evaluate these agents:

### 1. Install FluxLoop

```bash
pip install fluxloop fluxloop-cli
```

### 2. Add FluxLoop Instrumentation

Add the `@fluxloop.agent()` decorator to trace agent execution:

```python
import fluxloop

@fluxloop.agent()
def run_customer_support_agent(query: str):
    # Your agent code here
    return graph.invoke({"messages": [query]})
```

### 3. Generate Test Inputs

Create diverse test scenarios for your agent:

```bash
fluxloop generate inputs --limit 50
```

### 4. Run Simulations

Execute batch experiments with different configurations:

```bash
fluxloop run experiment
```

### 5. Analyze Results

Parse and analyze agent performance:

```bash
fluxloop parse experiment experiments/<experiment_dir>
```

For detailed FluxLoop integration guides, see the [FluxLoop documentation](https://fluxloop.io/).

---

## Repository Structure

```
fluxloop-tutorials/
├── README.md                          # This file
├── langgraph/                         # LangGraph framework tutorials
│   └── customer-support/              # Customer support agent example
│       ├── README.md
│       ├── pyproject.toml
│       └── src/
│           └── customer_support/
│               ├── main.py            # CLI entry point
│               ├── graphs/            # Part 1-4 implementations
│               ├── tools/             # Booking and policy tools
│               ├── data/              # Database utilities
│               └── utils/             # Shared helpers
└── [more frameworks coming soon]      # LlamaIndex, CrewAI, etc.
```

---

## Roadmap

We're continuously expanding this collection with more frameworks and use cases:

- [x] LangGraph: Customer Support Agent
- [ ] LangGraph: Research Assistant
- [ ] LangGraph: Code Review Agent
- [ ] LlamaIndex: RAG-based Q&A Agent
- [ ] CrewAI: Multi-Agent Collaboration
- [ ] Custom Framework: Simple Reasoning Agent

---

## Contributing

We welcome contributions! If you have an interesting agent implementation you'd like to share:

1. Fork this repository
2. Add your tutorial in a new directory with:
   - Complete source code
   - README with setup instructions
   - Example usage and expected outputs
3. Submit a pull request

Please ensure your tutorial:
- Is self-contained and reproducible
- Includes clear documentation
- Demonstrates FluxLoop integration (or can be easily integrated)
- Follows the existing structure and style

---

## Requirements

- Python 3.11+ (for most tutorials)
- API keys for LLM providers (OpenAI, Anthropic, etc.)
- Optional: FluxLoop SDK for instrumentation and evaluation

Specific requirements are listed in each tutorial's README.

---

## License

This repository is open-source and available under the MIT License. Individual tutorials may use different licenses—check each tutorial's directory for details.

---

## Resources

- **FluxLoop**: [GitHub](https://github.com/chuckgu/fluxloop) | [Documentation](https://fluxloop.io/)
- **LangGraph**: [Docs](https://langchain-ai.github.io/langgraph/) | [Tutorials](https://langchain-ai.github.io/langgraph/tutorials/)
- **LangChain**: [Docs](https://python.langchain.com/)
- **Community**: [FluxLoop Issues](https://github.com/chuckgu/fluxloop/issues)

---

## Questions or Feedback?

- Open an issue in this repository
- Check the [FluxLoop community](https://github.com/chuckgu/fluxloop/issues) for questions about instrumentation
- Each tutorial has its own README with specific troubleshooting tips

Happy building! 🚀

