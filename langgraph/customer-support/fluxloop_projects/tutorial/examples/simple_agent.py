"""Sample agent implementation for FluxLoop testing."""

import random
import time
from typing import Any, Dict

import fluxloop


@fluxloop.agent(name="SimpleAgent")
def run(input_text: str) -> str:
    """Main agent entry point."""
    processed = process_input(input_text)
    response = generate_response(processed)
    time.sleep(random.uniform(0.1, 0.5))
    return response


@fluxloop.prompt(model="simple-model")
def generate_response(processed_input: Dict[str, Any]) -> str:
    intent = processed_input.get("intent", "unknown")
    responses = {
        "greeting": "Hello! How can I help you today?",
        "help": "I can assist you with various tasks. What would you like to know?",
        "capabilities": "I can answer questions, provide information, and help with tasks.",
        "demo": "Here's an example: You can ask me about any topic and I'll try to help.",
        "unknown": "I'm not sure I understand. Could you please rephrase?",
    }
    return responses.get(intent, responses["unknown"])


@fluxloop.tool(description="Process and analyze input text")
def process_input(text: str) -> Dict[str, Any]:
    text_lower = text.lower()

    intent = "unknown"
    if any(word in text_lower for word in ["hello", "hi", "hey"]):
        intent = "greeting"
    elif any(word in text_lower for word in ["help", "start", "begin"]):
        intent = "help"
    elif any(word in text_lower for word in ["can you", "what can", "capabilities"]):
        intent = "capabilities"
    elif "example" in text_lower or "demo" in text_lower:
        intent = "demo"

    return {
        "original": text,
        "intent": intent,
        "word_count": len(text.split()),
        "has_question": "?" in text,
    }


if __name__ == "__main__":
    with fluxloop.instrument("test_run"):
        result = run("Hello, what can you help me with?")
        print(f"Result: {result}")
