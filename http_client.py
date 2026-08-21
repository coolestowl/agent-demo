from httpx import AsyncClient, HTTPStatusError
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
from tenacity import retry_if_exception_type, stop_after_attempt

transport = AsyncTenacityTransport(
    RetryConfig(
        retry=retry_if_exception_type(HTTPStatusError),
        wait=wait_retry_after(max_wait=300),
        stop=stop_after_attempt(5),
        reraise=True,
    ),
    validate_response=lambda r: r.raise_for_status(),
)

http_client = AsyncClient(transport=transport)
