"""Anthropic Claude API client.

All Claude calls in the project go through this module (never from routers).
Mirrors the FinnhubClient design: typed exceptions that routers can map to
proper HTTP responses:

- ClaudeAuthError        -> credentials missing or rejected
- ClaudeRateLimitError   -> HTTP 429
- ClaudeUnavailableError -> timeout, connection error, or 5xx
- ClaudeError            -> base class / any other problem

Two providers (CLAUDE_PROVIDER in .env):
- "anthropic" (default): direct Claude API via ANTHROPIC_API_KEY.
- "bedrock": Claude on Amazon Bedrock — billed to the AWS account (credits work
  there). Auth comes from the standard AWS credential chain (env vars,
  ~/.aws/credentials, etc.). New Claude models on Bedrock are on-demand only
  through a cross-region "inference profile" ID (e.g. "us.anthropic.<model>"),
  not the bare "anthropic.<model>" ID — see _resolve_bedrock_model_id below.
"""

import anthropic
from anthropic import AsyncAnthropic, AsyncAnthropicBedrock

from app.core.config import get_settings


def _resolve_bedrock_model_id(model: str) -> str:
    """Turn a bare model id ("claude-sonnet-4-6") or the plain Bedrock id
    ("anthropic.claude-sonnet-4-6") into the cross-region inference profile id
    Bedrock actually accepts for on-demand invocation ("us.anthropic.claude-sonnet-4-6").
    Already-qualified ids (us./global./eu. prefix) are left untouched.
    """
    if model.startswith(("us.", "global.", "eu.")):
        return model
    bare = model.removeprefix("anthropic.")
    return f"us.anthropic.{bare}"


class ClaudeError(Exception):
    """Base error for anything that goes wrong talking to the Claude API."""


class ClaudeAuthError(ClaudeError):
    pass


class ClaudeRateLimitError(ClaudeError):
    pass


class ClaudeUnavailableError(ClaudeError):
    pass


class ClaudeClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        provider: str = "anthropic",
        aws_region: str = "us-east-1",
    ) -> None:
        self._api_key = api_key
        self._provider = provider
        if provider == "bedrock":
            self.model = _resolve_bedrock_model_id(model)
            self._client = AsyncAnthropicBedrock(aws_region=aws_region)
        else:
            self.model = model
            # The SDK refuses to construct without a key; the real check is in generate().
            self._client = AsyncAnthropic(api_key=api_key or "unset")

    async def aclose(self) -> None:
        await self._client.close()

    async def generate(self, system: str, user_content: str, max_tokens: int = 2000) -> str:
        """One non-streaming completion; returns the concatenated text blocks."""
        if self._provider == "anthropic" and not self._api_key:
            raise ClaudeAuthError("ANTHROPIC_API_KEY is not set in .env")

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_content}],
            )
        # Auth/RateLimit/PermissionDenied are APIStatusError subclasses — keep them first.
        except anthropic.AuthenticationError as exc:
            raise ClaudeAuthError("The API rejected the credentials") from exc
        except anthropic.PermissionDeniedError as exc:
            # On Bedrock this usually means model access is not enabled for the
            # region, or the AWS credentials lack bedrock permissions.
            raise ClaudeAuthError(f"Access denied: {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            raise ClaudeRateLimitError("Claude rate limit exceeded") from exc
        except anthropic.APIConnectionError as exc:
            raise ClaudeUnavailableError(f"Claude did not respond: {exc}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ClaudeUnavailableError(
                    f"Claude server error: {exc.status_code}"
                ) from exc
            raise ClaudeError(f"Claude error {exc.status_code}: {exc.message}") from exc
        except Exception as exc:  # e.g. AWS credential-chain errors raised by boto
            raise ClaudeUnavailableError(f"Claude request failed: {exc}") from exc

        text = "".join(block.text for block in response.content if block.type == "text")
        if not text:
            raise ClaudeError("Claude returned an empty response")
        return text


_client: ClaudeClient | None = None


def get_claude_client() -> ClaudeClient:
    """FastAPI dependency — one shared client for the whole process."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = ClaudeClient(
            settings.anthropic_api_key,
            settings.anthropic_model,
            provider=settings.claude_provider,
            aws_region=settings.aws_region,
        )
    return _client


async def close_claude_client() -> None:
    """Close the shared client (called from the app lifespan on shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
