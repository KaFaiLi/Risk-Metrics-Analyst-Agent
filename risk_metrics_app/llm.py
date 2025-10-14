import asyncio
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Coroutine

from langchain.schema import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .config import LLM_RETRY_DELAY, MAX_LLM_ATTEMPTS, MAX_LLM_CONCURRENCY, logger
from .prompts import create_portfolio_summary_prompt

LLMFactory = Callable[[], ChatGoogleGenerativeAI]
LLMRequest = Dict[str, Any]


async def invoke_llm_with_retry(
    message: HumanMessage,
    llm_factory: LLMFactory,
    semaphore: asyncio.Semaphore,
    max_attempts: int = MAX_LLM_ATTEMPTS,
    retry_delay: float = LLM_RETRY_DELAY,
) -> str:
    """Invoke the provided LLM with retry logic and concurrency control."""
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        llm = llm_factory()
        try:
            logger.info("LLM request attempt %s", attempt)
            async with semaphore:
                if hasattr(llm, "ainvoke"):
                    response = await llm.ainvoke([message])
                else:
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(None, llm.invoke, [message])
            content = response.content
            logger.info("LLM request succeeded on attempt %s", attempt)
            return content if isinstance(content, str) else str(content)
        except Exception as error:  # noqa: BLE001 - broad for retry logic
            last_error = error
            logger.warning("LLM request failed on attempt %s: %s", attempt, error)
            if attempt < max_attempts:
                await asyncio.sleep(retry_delay)

    logger.error("LLM request exhausted retries: %s", last_error)
    return f"Error generating AI analysis: {str(last_error)}\n\nPlease check your Google API key."


async def process_llm_requests(
    requests: Iterable[LLMRequest],
    max_concurrent: int = MAX_LLM_CONCURRENCY,
    max_attempts: int = MAX_LLM_ATTEMPTS,
    retry_delay: float = LLM_RETRY_DELAY,
) -> List[Tuple[LLMRequest, str]]:
    """Process multiple LLM requests concurrently with rate limiting and retry."""
    request_list = list(requests)
    semaphore = asyncio.Semaphore(max_concurrent)
    logger.info("Processing %s LLM request(s) with max concurrency %s", len(request_list), max_concurrent)

    async def handle_request(request: LLMRequest) -> Tuple[LLMRequest, str]:
        logger.info("Dispatching LLM request for metric %s", request["metric"])

        def llm_factory() -> ChatGoogleGenerativeAI:
            return ChatGoogleGenerativeAI(model="gemini-flash-lite-latest", temperature=0.7)

        message = HumanMessage(
            content=[
                {"type": "text", "text": request["prompt_text"]},
                {"type": "image_url", 
                 "image_url": {
                     "url": f"data:image/png;base64,{request['img_base64']}"
                     }
                },
            ]
        )

        content = await invoke_llm_with_retry(
            message,
            llm_factory,
            semaphore,
            max_attempts=max_attempts,
            retry_delay=retry_delay,
        )
        return request, content

    tasks = [handle_request(req) for req in request_list]
    return await asyncio.gather(*tasks)


async def invoke_text_prompt(
    prompt_text: str,
    max_attempts: int = MAX_LLM_ATTEMPTS,
    retry_delay: float = LLM_RETRY_DELAY,
) -> str:
    """Invoke the LLM with a text-only prompt and retry handling."""
    semaphore = asyncio.Semaphore(1)
    logger.info("Invoking text-only LLM prompt")

    message = HumanMessage(content=prompt_text)

    def llm_factory() -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(model="gemini-flash-lite-latest", temperature=0.7)

    return await invoke_llm_with_retry(
        message,
        llm_factory,
        semaphore,
        max_attempts=max_attempts,
        retry_delay=retry_delay,
    )


def run_async_task(coro: Coroutine[Any, Any, Any]):
    """Run an async coroutine, handling existing event loops if necessary."""
    try:
        return asyncio.run(coro)
    except RuntimeError as error:
        if "event loop is running" in str(error):
            logger.info("Detected running event loop; spawning dedicated loop for coroutine")
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(coro)
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        raise


def get_portfolio_summary(metrics_analyses: List[dict]) -> str:
    """Generate a portfolio-level summary using the LLM."""
    try:
        prompt = create_portfolio_summary_prompt(metrics_analyses)
        response_content = run_async_task(
            invoke_text_prompt(prompt, max_attempts=MAX_LLM_ATTEMPTS, retry_delay=LLM_RETRY_DELAY)
        )
        return response_content
    except Exception as error:  # noqa: BLE001 - propagate readable error upstream
        return f"Error generating portfolio summary: {str(error)}\n\nPlease check your Google API key."


__all__ = [
    "LLMRequest",
    "get_portfolio_summary",
    "invoke_llm_with_retry",
    "invoke_text_prompt",
    "process_llm_requests",
    "run_async_task",
]
