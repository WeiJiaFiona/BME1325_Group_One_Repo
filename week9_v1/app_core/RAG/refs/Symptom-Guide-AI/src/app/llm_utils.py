"""
LLM utilities: model loading and chain construction.
"""

import os
from typing import Optional

import streamlit as st
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain_core.output_parsers import StrOutputParser

from src.app.config import MedicalConfig


def set_mode(mode: str) -> None:
    """Set the current AI mode (Local or Cloud).

    Stores the mode in Streamlit session state so it is
    per-session and thread-safe.

    Parameters
    ----------
    mode : str
        Either "Local (Ollama)" or "Cloud (HuggingFace)"; the selected
        backend is used for all subsequent calls to :func:`get_llm`.
    """
    st.session_state["llm_mode"] = mode


def get_mode() -> str:
    """Return the currently selected AI backend mode.

    Useful for debugging or conditional logic external to this module.
    """
    return st.session_state.get("llm_mode", "Local (Ollama)")


def get_llm(temperature: float = 0.3):
    """Get the appropriate LLM based on current mode."""
    mode = get_mode()
    config = MedicalConfig()

    if mode == "Local (Ollama)":
        return ChatOllama(model=config.LLM_MODEL, temperature=temperature)

    # Cloud mode (HuggingFace)
    if not os.environ.get("HUGGINGFACEHUB_API_TOKEN"):
        raise ValueError("HuggingFace API token not set. Please configure in sidebar.")

    return HuggingFaceEndpoint(
        repo_id="meta-llama/Llama-3.3-70B-Instruct",
        temperature=temperature
    )


def build_chain(prompt_template: str, temperature: float = 0.3):
    """Build a LangChain chain for text generation (single-template, backward compat).

    Uses a single HumanMessage template. Suitable for simple extraction tasks
    (keyword extraction, symptom accumulation) but NOT for conversation.
    """
    llm = get_llm(temperature)
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    return chain


def build_chat_chain(system_template: str, human_template: str, temperature: float = 0.3):
    """Build a chain with proper System + Human message separation.

    This is the correct way to build conversational chains.
    The system message sets the AI's identity and rules.
    The human message contains the user's context and question.
    Llama3 treats these differently — the system message becomes
    the AI's personality, preventing self-introduction loops.

    Parameters
    ----------
    system_template : str
        System message template (identity, personality, rules).
    human_template : str
        Human message template (chat history, symptoms, user input).
    temperature : float, optional
        Sampling temperature for the LLM.

    Returns
    -------
    A LangChain ``Chain`` object ready for ``.stream`` or ``.invoke``.
    """
    llm = get_llm(temperature)
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_template),
        HumanMessagePromptTemplate.from_template(human_template),
    ])
    return prompt | llm | StrOutputParser()
