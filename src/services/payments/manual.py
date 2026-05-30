"""Manual payment provider + invoice generation.

The manual provider allows admins to mark payments as received, activating
subscriptions without an external payment gateway.  Also generates simple
HTML invoices.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.sql_models import Invoice, Subscription, User
from src.services.payments.dispatcher import PaymentProvider, register_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Invoice HTML template
# ---------------------------------------------------------------------------

INVOICE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Invoice {invoice_id}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 40px auto; color: #1a1a2e; }}
  h1 {{ font-size: 28px; margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 14px; margin-bottom: 30px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
  th {{ background: #f0f0f5; text-align: left; padding: 10px 12px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }}
  td {{ padding: 12px; border-bottom: 1px solid #e0e0e8; }}
  .total {{ font-size: 20px; font-weight: 700; text-align: right; padding-top: 16px; }}
  .footer {{ margin-top: 40px; font-size: 13px; color: #888; border-top: 1px solid #e0e0e8; padding-top: 16px; }}
  .status {{ display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
  .status-paid {{ background: #d4edda; color: #155724; }}
  .status-pending {{ background: #fff3cd; color: #856404; }}
  .status-void {{ background: #f8d7da; color: #721c24; }}
</style>
</head>
<body>
  <h1>Kaf Extract</h1>
  <p class="meta">
    Invoice #{invoice_id}<br>
    Date: {date}<br>
    {paid_line}
  </p>

  <h2>Bill To</h2>
  <p>{customer_name}<br>{customer_email}</p>

  <table>
    <thead>
      <tr><th>Description</th><th style="text-align:right">Amount</th></tr>
    </thead>
    <tbody>
      <tr>
        <td>{plan_name} Plan — {period}</td>
        <td style="text-align:right">${amount_dollars:.2f} {currency_upper}</td>
      </tr>
    </tbody>
  </table>

  <p class="total">Total: ${amount_dollars:.2f} {currency_upper}</p>
  <p><span class="status status-{status_css}">{status_label}</span></p>

  <div class="footer">
    Kaf Extract &mdash; API-First Data Extraction Service<br>
    Invoice generated automatically. Contact support@kafextract.com for questions.
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Invoice generation helper
# ---------------------------------------------------------------------------


def generate_invoice_html(
    *,
    invoice_id: str,
    customer_name: str,
    customer_email: str,
    plan: str,
    amount_cents: int | None = None,
    currency: str = "usd",
    status: str = "pending",
    paid_at: datetime | None = None,
) -> str:
    """Render an HTML invoice string from the template above."""
    plan_info = settings.plans.get(plan, settings.plans["hobby"])
    plan_name = plan_info["name"]
    amount = amount_cents or plan_info["price_cents"]

    status_css_map = {
        "paid": "paid",
        "pending": "pending",
        "void": "void",
        "refunded": "void",
    }
    status_display = {"pending": "PENDING", "paid": "PAID", "void": "VOID", "refunded": "REFUNDED"}

    paid_line = f"Paid: {paid_at.strftime('%B %d, %Y')}" if paid_at else ""
    if not paid_line:
        paid_line = ""

    return INVOICE_HTML_TEMPLATE.format(
        invoice_id=invoice_id,
        date=datetime.now(UTC).strftime("%B %d, %Y"),
        paid_line=paid_line,
        customer_name=customer_name or "Valued Customer",
        customer_email=customer_email,
        plan_name=plan_name,
        period="Monthly",
        amount_dollars=amount / 100.0,
        currency_upper=currency.upper(),
        status_css=status_css_map.get(status, "pending"),
        status_label=status_display.get(status, "PENDING"),
    )


async def save_invoice(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID | None,
    plan: str,
    amount_cents: int,
    currency: str = "usd",
    status: str = "pending",
    provider: str = "manual",
    provider_invoice_id: str | None = None,
    customer_name: str = "",
    customer_email: str = "",
) -> Invoice:
    """Create an Invoice DB record and write the HTML file."""
    invoice_id = uuid.uuid4()

    html = generate_invoice_html(
        invoice_id=str(invoice_id),
        customer_name=customer_name,
        customer_email=customer_email,
        plan=plan,
        amount_cents=amount_cents,
        currency=currency,
        status=status,
    )

    # Ensure invoices directory exists
    invoices_dir = Path(settings.invoices_dir)
    invoices_dir.mkdir(parents=True, exist_ok=True)

    html_path = invoices_dir / f"{invoice_id}.html"
    html_path.write_text(html, encoding="utf-8")

    invoice = Invoice(
        id=invoice_id,
        user_id=user_id,
        subscription_id=subscription_id,
        amount=amount_cents,
        currency=currency,
        status=status,
        provider=provider,
        provider_invoice_id=provider_invoice_id,
        plan=plan,
        html_path=str(html_path),
        paid_at=datetime.now(UTC) if status == "paid" else None,
    )
    db.add(invoice)
    await db.flush()

    logger.info("Generated invoice %s for user %s (plan=%s, amount=%d)",
                 invoice_id, user_id, plan, amount_cents)

    return invoice


# ---------------------------------------------------------------------------
# Manual payment provider
# ---------------------------------------------------------------------------


@register_provider
class ManualPaymentProvider(PaymentProvider):
    """Manual / admin-driven payment provider.

    Admins use the dashboard to mark payments as received, which activates
    or extends a user's subscription.  Also generates invoices.
    """

    name = "manual"

    # ------------------------------------------------------------------
    # PaymentProvider interface
    # ------------------------------------------------------------------

    async def create_checkout(
        self, user_id: str, plan: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Manual checkout: no external URL; just return a message."""
        return {
            "url": "",
            "provider": "manual",
            "message": (
                "Manual payment: an admin will activate your subscription. "
                "Contact support for payment instructions."
            ),
        }

    async def handle_webhook(
        self, payload: dict[str, Any], headers: dict[str, str], *, raw_body: bytes | str = b""
    ) -> dict[str, Any]:
        """Manual provider has no webhooks."""
        logger.warning("Manual provider received webhook — ignoring")
        return {"status": "ignored", "provider": "manual"}

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Manual provider cancellation is handled via DB."""
        return {
            "status": "canceled",
            "subscription_id": subscription_id,
            "provider": "manual",
        }

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Manual provider: subscription is looked up from DB."""
        return {
            "subscription_id": subscription_id,
            "provider": "manual",
        }

    def verify_signature(
        self, payload: bytes | str, headers: dict[str, str]
    ) -> bool:
        """Manual provider has no signature verification."""
        return True

    # ------------------------------------------------------------------
    # Manual-specific operations (used by admin endpoints)
    # ------------------------------------------------------------------

    @staticmethod
    async def activate_subscription(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        plan: str,
    ) -> Subscription:
        """Mark a manual payment as received → activate subscription."""
        # Deactivate any existing active subscriptions for this user
        await db.execute(
            update(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
            .values(status="canceled")
        )

        # Create new subscription
        from src.services.plans import get_plan_by_key
        plan_data = await get_plan_by_key(db, plan)
        plan_info = plan_data or settings.plans.get(plan, settings.plans["hobby"])
        now = datetime.now(UTC)
        # Simple monthly billing cycle
        from datetime import timedelta
        period_end = now + timedelta(days=30)

        sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan=plan,
            status="active",
            provider="manual",
            current_period_start=now,
            current_period_end=period_end,
        )
        db.add(sub)
        await db.flush()

        # Generate invoice
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        await save_invoice(
            db,
            user_id=user_id,
            subscription_id=sub.id,
            plan=plan,
            amount_cents=plan_info["price_cents"],
            currency="usd",
            status="paid",
            provider="manual",
            customer_name=user.name if user and user.name else "",
            customer_email=user.email if user else "",
        )

        logger.info(
            "Manual subscription activated for user %s plan %s", user_id, plan
        )

        return sub
