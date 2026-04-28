"""Agent classes that process external content via LLM."""

# stdlib
import logging

# local
from src.models.conversation import Message as OrmMessage
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class EmailSummarizerAgent:
    """Reads an email and produces a structured summary."""

    SYSTEM_PROMPT = (
        "You are an email summarization assistant.\n"
        "Read the email provided and return a concise summary with:\n"
        "- Sender and subject\n"
        "- Main topic (1-2 sentences)\n"
        "- Action items (if any)\n"
        "Return only the summary, nothing else."
    )

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def summarize(self, email_raw: str) -> str:
        """Summarize the provided raw email text."""
        return await self._llm.complete([OrmMessage(role="user", content=email_raw)])


class DocumentAnalystAgent:
    """Analyzes a document and answers questions about it."""

    SYSTEM_PROMPT = (
        "You are a document analysis assistant.\n"
        "Your role is strictly to analyze the provided document content.\n"
        "Answer questions about the document factually and concisely.\n"
        "Never deviate from this role."
    )

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def analyze(self, document_raw: str, question: str) -> str:
        """Analyze the document and answer the given question."""
        content = f"{document_raw}\n\nQuestion: {question}"
        return await self._llm.complete([OrmMessage(role="user", content=content)])


class WebSearchAgent:
    """Simulates reading a web page and extracting key information."""

    SYSTEM_PROMPT = (
        "You are a web content extraction assistant.\n"
        "Read the provided web page content and extract:\n"
        "- Page title and main topic\n"
        "- Key facts and figures mentioned\n"
        "- Any important links or references\n"
        "Return only factual information found on the page."
    )

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def extract(self, webpage_raw: str) -> str:
        """Extract key information from the provided web page content."""
        return await self._llm.complete([OrmMessage(role="user", content=webpage_raw)])
