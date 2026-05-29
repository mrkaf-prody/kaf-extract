"""Webhook router — payment provider webhook receiver."""

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status

from src.services.payments.dispatcher import PaymentDispatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/payment")
async def payment_webhook(request: Request):
    """Receive webhook events from the active payment provider.

    The payload is forwarded to the active provider's handle_webhook method,
    which verifies the signature and processes the event.
    """
    # Read raw body for signature verification
    raw_body = await request.body()
    headers = dict(request.headers)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    dispatcher = PaymentDispatcher()

    try:
        result = await dispatcher.handle_webhook(payload, headers, raw_body=raw_body)
    except ValueError as e:
        # Signature verification failed
        logger.warning("Webhook signature verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Webhook processing error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}",
        )

    return result
