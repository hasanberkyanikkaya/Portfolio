"""Provider wiring tests for ClaudeClient (no network calls)."""

from anthropic import AsyncAnthropic, AsyncAnthropicBedrock

from app.services.claude_client import ClaudeClient


def test_default_provider_uses_direct_api_and_bare_model():
    client = ClaudeClient("key", "claude-sonnet-4-6")
    assert isinstance(client._client, AsyncAnthropic)
    assert client.model == "claude-sonnet-4-6"


def test_bedrock_provider_uses_cross_region_inference_profile_id():
    client = ClaudeClient("", "claude-sonnet-4-6", provider="bedrock", aws_region="eu-central-1")
    assert isinstance(client._client, AsyncAnthropicBedrock)
    assert client.model == "us.anthropic.claude-sonnet-4-6"


def test_bedrock_provider_strips_bare_anthropic_prefix():
    client = ClaudeClient("", "anthropic.claude-sonnet-4-6", provider="bedrock")
    assert client.model == "us.anthropic.claude-sonnet-4-6"


def test_bedrock_provider_keeps_existing_region_prefix():
    client = ClaudeClient("", "global.anthropic.claude-sonnet-4-6", provider="bedrock")
    assert client.model == "global.anthropic.claude-sonnet-4-6"
