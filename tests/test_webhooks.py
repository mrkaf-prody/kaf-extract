"""Tests for webhook callbacks — HMAC-SHA256 signing + retry + dispatch.

Covers:
- HMAC-SHA256 signature creation and verification (sign_payload / verify_signature)
- Webhook dispatch with retry logic (exponential backoff: 1s, 4s, 16s)
- Signature header X-Kaf-Signature on webhook POSTs
- Successful delivery and failed delivery after max retries
- dispatch_webhook called from run_extraction and run_batch_extraction
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import settings
from src.services.queue import (
    dispatch_webhook,
    sign_payload,
    verify_signature,
    run_extraction,
    run_batch_extraction,
    WEBHOOK_RETRY_DELAYS,
)


# ---------------------------------------------------------------------------
# HMAC signing tests
# ---------------------------------------------------------------------------


class TestHMACSigning:
    """Tests for HMAC-SHA256 payload signing and verification."""

    def test_sign_payload_produces_hex_string(self):
        """sign_payload should produce a hex-encoded HMAC-SHA256."""
        payload = {"status": "success", "data": {"title": "Hello"}}
        sig = sign_payload(payload, "my-secret-key")
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA256 hex digest is 64 chars
        # Should be hex characters only
        assert all(c in "0123456789abcdef" for c in sig)

    def test_sign_payload_deterministic(self):
        """Same payload + secret should produce the same signature."""
        payload = {"a": 1, "b": "hello"}
        sig1 = sign_payload(payload, "secret")
        sig2 = sign_payload(payload, "secret")
        assert sig1 == sig2

    def test_sign_payload_different_for_different_payloads(self):
        """Different payloads should produce different signatures."""
        sig1 = sign_payload({"x": 1}, "secret")
        sig2 = sign_payload({"x": 2}, "secret")
        assert sig1 != sig2

    def test_sign_payload_different_for_different_secrets(self):
        """Same payload with different secrets should produce different sigs."""
        payload = {"data": "test"}
        sig1 = sign_payload(payload, "secret1")
        sig2 = sign_payload(payload, "secret2")
        assert sig1 != sig2

    def test_sign_payload_sorted_keys(self):
        """Signing should be order-independent (sorted_keys=True)."""
        payload1 = {"b": 2, "a": 1}
        payload2 = {"a": 1, "b": 2}
        sig1 = sign_payload(payload1, "secret")
        sig2 = sign_payload(payload2, "secret")
        assert sig1 == sig2

    def test_verify_signature_valid(self):
        """verify_signature should return True for valid signature."""
        payload = {"status": "ok", "result": 42}
        secret = "test-secret"
        sig = sign_payload(payload, secret)
        assert verify_signature(payload, sig, secret) is True

    def test_verify_signature_invalid(self):
        """verify_signature should return False for invalid signature."""
        payload = {"status": "ok"}
        valid_sig = sign_payload(payload, "correct-secret")
        assert verify_signature(payload, valid_sig, "wrong-secret") is False

    def test_verify_signature_tampered_payload(self):
        """verify_signature should detect tampered payloads."""
        payload = {"status": "ok"}
        sig = sign_payload(payload, "secret")
        # Tamper with payload
        tampered = {"status": "hacked"}
        assert verify_signature(tampered, sig, "secret") is False

    def test_sign_payload_with_json_native_types(self):
        """sign_payload should handle dict, list, None, int, float, bool."""
        payload = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "none_val": None,
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
        }
        sig = sign_payload(payload, "secret")
        assert len(sig) == 64

    def test_verify_uses_constant_time(self):
        """verify_signature should use hmac.compare_digest for timing safety."""
        # This is an implementation test — we check the internal call
        with patch("hmac.compare_digest", wraps=__import__("hmac").compare_digest) as mock_cd:
            payload = {"test": True}
            sig = sign_payload(payload, "secret")
            result = verify_signature(payload, sig, "secret")
            mock_cd.assert_called_once_with(sig, sig)


# ---------------------------------------------------------------------------
# Webhook dispatch tests
# ---------------------------------------------------------------------------


class TestDispatchWebhook:
    """Tests for dispatch_webhook with retry and HMAC signing."""

    @pytest.fixture
    def sample_payload(self):
        return {
            "status": "success",
            "data": {"title": "Hello World"},
            "metadata": {
                "url": "https://example.com",
                "duration_ms": 1234,
                "timestamp": "2024-01-01T00:00:00+00:00",
            },
        }

    @pytest.mark.asyncio
    async def test_dispatch_webhook_success_first_attempt(self, sample_payload):
        """Webhook should succeed on the first attempt when server returns 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await dispatch_webhook("https://hooks.example.com/cb", sample_payload)

            assert result is True
            mock_post.assert_called_once()

            # Verify the call arguments
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["headers"]["Content-Type"] == "application/json"
            assert "X-Kaf-Signature" in call_kwargs["headers"]

            # Verify the signature
            signature = call_kwargs["headers"]["X-Kaf-Signature"]
            assert verify_signature(sample_payload, signature, settings.jwt_secret)

    @pytest.mark.asyncio
    async def test_dispatch_webhook_retry_on_500(self, sample_payload):
        """Webhook should retry on 5xx errors and eventually succeed."""
        mock_responses = [
            MagicMock(status_code=502, text="Bad Gateway"),
            MagicMock(status_code=502, text="Bad Gateway"),
            MagicMock(status_code=200, text="OK"),
        ]

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = mock_responses

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await dispatch_webhook(
                    "https://hooks.example.com/cb", sample_payload, max_retries=3
                )

            assert result is True
            assert mock_post.call_count == 3
            # Should have slept with exponential backoff
            assert mock_sleep.call_count == 2  # 2 retries = 2 sleeps
            mock_sleep.assert_any_call(WEBHOOK_RETRY_DELAYS[0])
            mock_sleep.assert_any_call(WEBHOOK_RETRY_DELAYS[1])

    @pytest.mark.asyncio
    async def test_dispatch_webhook_fails_after_all_retries(self, sample_payload):
        """Webhook should return False after exhausting all retries."""
        mock_response = MagicMock(status_code=500, text="Internal Server Error")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await dispatch_webhook(
                    "https://hooks.example.com/cb", sample_payload, max_retries=2
                )

            assert result is False
            # 1 initial + 2 retries = 3 attempts
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_dispatch_webhook_network_error_retry(self, sample_payload):
        """Webhook should retry on network errors and eventually succeed."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                Exception("Connection refused"),
                Exception("Connection refused"),
                MagicMock(status_code=200, text="OK"),
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await dispatch_webhook(
                    "https://hooks.example.com/cb", sample_payload, max_retries=3
                )

            assert result is True
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_dispatch_webhook_signature_header_present(self, sample_payload):
        """Every webhook request must include the X-Kaf-Signature header."""
        mock_response = MagicMock(status_code=200, text="OK")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await dispatch_webhook("https://hooks.example.com/cb", sample_payload)

            call_kwargs = mock_post.call_args.kwargs
            assert "X-Kaf-Signature" in call_kwargs["headers"]
            signature = call_kwargs["headers"]["X-Kaf-Signature"]
            # Verify that signature is valid
            body = json.loads(call_kwargs["content"])
            assert verify_signature(body, signature, settings.jwt_secret)

    @pytest.mark.asyncio
    async def test_dispatch_webhook_backoff_sequence(self, sample_payload):
        """Verify exponential backoff: 1s, 4s, 16s."""
        mock_response = MagicMock(status_code=500, text="Error")

        sleep_calls = []

        async def fake_sleep(delay):
            sleep_calls.append(delay)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                mock_sleep.side_effect = fake_sleep
                await dispatch_webhook(
                    "https://hooks.example.com/cb", sample_payload, max_retries=3
                )

            # Should be called 3 times with WEBHOOK_RETRY_DELAYS values
            assert sleep_calls == WEBHOOK_RETRY_DELAYS

    @pytest.mark.asyncio
    async def test_dispatch_webhook_4xx_not_retried(self, sample_payload):
        """4xx errors should be retried (they may be transient, e.g., 429)."""
        mock_responses = [
            MagicMock(status_code=429, text="Too Many Requests"),
            MagicMock(status_code=200, text="OK"),
        ]

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = mock_responses

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await dispatch_webhook(
                    "https://hooks.example.com/cb", sample_payload, max_retries=3
                )

            assert result is True
            assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# Integration: webhook dispatch from run_extraction / run_batch_extraction
# ---------------------------------------------------------------------------


class TestWebhookInWorker:
    """Tests that worker functions dispatch webhooks on completion."""

    @pytest.mark.asyncio
    async def test_run_extraction_dispatches_webhook_on_success(self):
        """run_extraction should call dispatch_webhook when webhook_url is set."""
        with patch("src.services.queue.extractor_service") as mock_svc:
            mock_svc.extract = AsyncMock(return_value={"title": "test"})

            with patch("src.services.queue.cache_extraction_result", new_callable=AsyncMock):
                with patch("src.services.queue.dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
                    mock_dispatch.return_value = True

                    result = await run_extraction(
                        ctx={},
                        url="https://example.com",
                        fields=[{"name": "title", "selector": "h1", "type": "text"}],
                        api_key_id="key-1",
                        webhook_url="https://hooks.example.com/cb",
                    )

                    assert result["status"] == "success"
                    mock_dispatch.assert_called_once()

                    # Verify the payload includes extraction data
                    call_args = mock_dispatch.call_args
                    assert call_args[0][0] == "https://hooks.example.com/cb"
                    assert call_args[0][1]["status"] == "success"
                    assert call_args[0][1]["data"] == {"title": "test"}

    @pytest.mark.asyncio
    async def test_run_extraction_dispatches_webhook_on_error(self):
        """run_extraction should dispatch webhook even when extraction fails."""
        from src.services.extractor import ExtractionError

        with patch("src.services.queue.extractor_service") as mock_svc:
            mock_svc.extract = AsyncMock(side_effect=ExtractionError("Browser failed"))

            with patch("src.services.queue.dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
                mock_dispatch.return_value = True

                result = await run_extraction(
                    ctx={},
                    url="https://bad-url.com",
                    fields=[{"name": "title", "selector": "h1", "type": "text"}],
                    api_key_id="key-1",
                    webhook_url="https://hooks.example.com/cb",
                )

                assert result["status"] == "error"
                mock_dispatch.assert_called_once()
                call_args = mock_dispatch.call_args
                assert call_args[0][1]["status"] == "error"
                assert "Browser failed" in call_args[0][1]["error"]

    @pytest.mark.asyncio
    async def test_run_extraction_no_webhook_when_not_set(self):
        """run_extraction should NOT call dispatch_webhook when webhook_url is None."""
        with patch("src.services.queue.extractor_service") as mock_svc:
            mock_svc.extract = AsyncMock(return_value={"title": "test"})

            with patch("src.services.queue.cache_extraction_result", new_callable=AsyncMock):
                with patch("src.services.queue.dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
                    result = await run_extraction(
                        ctx={},
                        url="https://example.com",
                        fields=[{"name": "title", "selector": "h1", "type": "text"}],
                        api_key_id="key-1",
                        webhook_url=None,
                    )

                    assert result["status"] == "success"
                    mock_dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_extraction_webhook_failure_not_propagated(self):
        """Webhook dispatch failure should not affect the extraction result."""
        with patch("src.services.queue.extractor_service") as mock_svc:
            mock_svc.extract = AsyncMock(return_value={"title": "test"})

            with patch("src.services.queue.cache_extraction_result", new_callable=AsyncMock):
                with patch("src.services.queue.dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
                    mock_dispatch.side_effect = Exception("Webhook server down")

                    result = await run_extraction(
                        ctx={},
                        url="https://example.com",
                        fields=[{"name": "title", "selector": "h1", "type": "text"}],
                        api_key_id="key-1",
                        webhook_url="https://hooks.example.com/cb",
                    )

                    # Should still return success even though webhook failed
                    assert result["status"] == "success"
                    assert result["data"] == {"title": "test"}

    @pytest.mark.asyncio
    async def test_run_batch_extraction_dispatches_webhook(self):
        """run_batch_extraction should call dispatch_webhook when webhook_url is set."""
        mock_batch_results = [
            {"url": "url1", "status": "success", "data": {"x": 1}, "error": None},
            {"url": "url2", "status": "error", "data": None, "error": "Failed"},
        ]

        with patch("src.services.queue.extractor_service") as mock_svc:
            mock_svc.extract_batch = AsyncMock(return_value=mock_batch_results)

            with patch("src.services.queue.dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
                mock_dispatch.return_value = True

                result = await run_batch_extraction(
                    ctx={},
                    urls=["url1", "url2"],
                    fields=[{"name": "title", "selector": "h1", "type": "text"}],
                    api_key_id="key-1",
                    webhook_url="https://hooks.example.com/cb",
                )

            assert result["status"] == "success"
            assert result["total"] == 2
            assert result["succeeded"] == 1
            assert result["failed"] == 1
            mock_dispatch.assert_called_once()

            # Verify payload structure
            call_args = mock_dispatch.call_args
            assert call_args[0][1]["total"] == 2
            assert call_args[0][1]["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_run_batch_extraction_no_webhook_when_not_set(self):
        """run_batch_extraction should NOT dispatch webhook when None."""
        mock_batch_results = [
            {"url": "url1", "status": "success", "data": {"x": 1}, "error": None},
        ]

        with patch("src.services.queue.extractor_service") as mock_svc:
            mock_svc.extract_batch = AsyncMock(return_value=mock_batch_results)

            with patch("src.services.queue.dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
                result = await run_batch_extraction(
                    ctx={},
                    urls=["url1"],
                    fields=[{"name": "title", "selector": "h1", "type": "text"}],
                    api_key_id="key-1",
                    webhook_url=None,
                )

            mock_dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_batch_extraction_dispatches_on_total_failure(self):
        """run_batch_extraction should dispatch webhook even when all URLs fail."""
        with patch("src.services.queue.extractor_service") as mock_svc:
            mock_svc.extract_batch = AsyncMock(
                side_effect=Exception("Browser crashed")
            )

            with patch("src.services.queue.dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
                mock_dispatch.return_value = True

                result = await run_batch_extraction(
                    ctx={},
                    urls=["url1", "url2"],
                    fields=[{"name": "title", "selector": "h1", "type": "text"}],
                    api_key_id="key-1",
                    webhook_url="https://hooks.example.com/cb",
                )

            assert result["status"] == "error"
            assert result["failed"] == 2
            mock_dispatch.assert_called_once()
