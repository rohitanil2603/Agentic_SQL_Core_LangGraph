"""
Shared LLM utilities for all agents.
Provides lazy initialization of ChatOpenAI instance using OpenRouter.
"""

import logging
import os

from langchain_openai import ChatOpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Lazy initialization of LLM
_llm = None


def get_llm():
    """
    Get or create shared LLM instance through OpenRouter.

    Environment variables:
        OPENROUTER_API_KEY: Your OpenRouter API key.
        OPENROUTER_MODEL: Model to use, e.g.
                          "openai/gpt-4o-mini"

    Returns:
        ChatOpenAI instance configured for OpenRouter.
    """
    global _llm

    if _llm is None:
        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is not set."
            )

        model = os.getenv(
            "OPENROUTER_MODEL",
            "openai/gpt-4o-mini"
        )

        _llm = ChatOpenAI(
            model=model,
            temperature=0,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        logger.info(
            "LLM instance created using OpenRouter: %s",
            model
        )

    return _llm