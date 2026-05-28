"""Voucher service — generation, redemption, listing, CSV export."""

import csv
import io
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.sql_models import (
    Subscription,
    User,
    Voucher,
    VoucherRedemption,
)


def _generate_code(prefix: str = "KAF") -> str:
    """Generate a unique voucher code like KAF-XXXX-XXXX."""
    block = secrets.token_hex(3).upper()  # 6 hex chars
    return f"{prefix}-{block[:4]}-{block[4:]}" if len(block) >= 6 else f"{prefix}-{block}"


class VoucherService:
    """Service for managing promotional vouchers."""

    # ------------------------------------------------------------------
    # Batch generation
    # ------------------------------------------------------------------

    async def generate_batch(
        self,
        db: AsyncSession,
        *,
        plan: str,
        quantity: int,
        duration_days: int = 30,
        extraction_credits: int = 0,
        max_uses: int = 1,
        expiry_date: datetime | None = None,
        prefix: str = "KAF",
        created_by: uuid.UUID | None = None,
    ) -> list[Voucher]:
        """Generate a batch of unique voucher codes.

        Returns the list of created Voucher ORM instances.
        """
        if quantity < 1 or quantity > 500:
            raise ValueError("Quantity must be between 1 and 500")

        if plan not in settings.plans:
            raise ValueError(
                f"Invalid plan '{plan}'. Valid plans: {list(settings.plans)}"
            )

        if expiry_date is None:
            expiry_date = datetime.now(UTC) + timedelta(days=365)

        # Generate unique codes
        existing_codes: set[str] = set()
        vouchers: list[Voucher] = []
        attempts = 0
        max_attempts = quantity * 20  # safety valve

        while len(vouchers) < quantity and attempts < max_attempts:
            attempts += 1
            code = _generate_code(prefix)

            if code in existing_codes:
                continue

            # Check DB uniqueness
            result = await db.execute(
                select(Voucher).where(Voucher.code == code)
            )
            if result.scalar_one_or_none() is not None:
                continue

            existing_codes.add(code)
            voucher = Voucher(
                id=uuid.uuid4(),
                code=code,
                plan=plan,
                duration_days=duration_days,
                extraction_credits=extraction_credits,
                expires_at=expiry_date,
                max_uses=max_uses,
                used_count=0,
                created_by=created_by,
                status="active",
            )
            db.add(voucher)
            vouchers.append(voucher)

        if len(vouchers) < quantity:
            raise RuntimeError(
                f"Could only generate {len(vouchers)}/{quantity} unique codes"
            )

        await db.flush()
        return vouchers

    # ------------------------------------------------------------------
    # Redeem
    # ------------------------------------------------------------------

    async def redeem_voucher(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        code: str,
        ip_address: str | None = None,
    ) -> dict:
        """Redeem a voucher for the given user, activating a subscription.

        Returns a dict with subscription details.
        """
        # Normalize code
        code = code.strip().upper()

        # Look up voucher
        result = await db.execute(
            select(Voucher).where(Voucher.code == code)
        )
        voucher = result.scalar_one_or_none()

        if voucher is None:
            raise ValueError("Invalid voucher code")

        # Status checks
        now = datetime.now(UTC)
        if voucher.status == "revoked":
            raise ValueError("This voucher has been revoked")
        if voucher.status == "exhausted":
            raise ValueError("This voucher has reached its maximum uses")
        if voucher.expires_at < now:
            voucher.status = "expired"
            await db.flush()
            raise ValueError("This voucher has expired")
        if voucher.used_count >= voucher.max_uses:
            voucher.status = "exhausted"
            await db.flush()
            raise ValueError("This voucher has reached its maximum uses")

        # Check if user already redeemed this voucher
        existing = await db.execute(
            select(VoucherRedemption).where(
                VoucherRedemption.voucher_id == voucher.id,
                VoucherRedemption.user_id == user_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("You have already redeemed this voucher")

        # Check if user already has an active subscription of this plan or higher
        # We'll allow stacking — just create/renew the subscription

        # Get user
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")

        # Create subscription
        period_end = now + timedelta(days=voucher.duration_days)
        sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan=voucher.plan,
            status="active",
            provider="voucher",
            current_period_start=now,
            current_period_end=period_end,
        )
        db.add(sub)

        # Record redemption
        redemption = VoucherRedemption(
            id=uuid.uuid4(),
            voucher_id=voucher.id,
            user_id=user_id,
            ip_address=ip_address,
        )
        db.add(redemption)

        # Update voucher usage
        voucher.used_count += 1
        if voucher.used_count >= voucher.max_uses:
            voucher.status = "exhausted"

        await db.flush()

        return {
            "subscription_id": str(sub.id),
            "plan": voucher.plan,
            "duration_days": voucher.duration_days,
            "period_end": period_end.isoformat(),
            "extraction_credits": voucher.extraction_credits,
        }

    # ------------------------------------------------------------------
    # List vouchers (admin)
    # ------------------------------------------------------------------

    async def list_vouchers(
        self,
        db: AsyncSession,
        *,
        status: str | None = None,
        plan: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Voucher], int]:
        """Return paginated list of vouchers with optional filters."""
        conditions = []

        if status:
            conditions.append(Voucher.status == status)
        if plan:
            conditions.append(Voucher.plan == plan)
        if search:
            conditions.append(
                or_(
                    Voucher.code.ilike(f"%{search}%"),
                )
            )

        # Count
        count_q = select(func.count(Voucher.id))
        if conditions:
            count_q = count_q.where(*conditions)
        total = (await db.execute(count_q)).scalar() or 0

        # Fetch
        q = select(Voucher).order_by(Voucher.created_at.desc())
        if conditions:
            q = q.where(*conditions)
        q = q.offset(offset).limit(limit)
        result = await db.execute(q)
        vouchers = list(result.scalars().all())

        return vouchers, total

    # ------------------------------------------------------------------
    # Export unused vouchers to CSV
    # ------------------------------------------------------------------

    async def export_unused_csv(self, db: AsyncSession) -> str:
        """Export all unused (active) vouchers as a CSV string."""
        result = await db.execute(
            select(Voucher)
            .where(Voucher.status == "active")
            .order_by(Voucher.created_at.desc())
        )
        vouchers = list(result.scalars().all())

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Code", "Plan", "DurationDays", "ExtractionCredits",
            "MaxUses", "UsedCount", "Status", "CreatedAt", "ExpiresAt",
        ])
        for v in vouchers:
            writer.writerow([
                v.code,
                v.plan,
                v.duration_days,
                v.extraction_credits,
                v.max_uses,
                v.used_count,
                v.status,
                v.created_at.isoformat() if v.created_at else "",
                v.expires_at.isoformat() if v.expires_at else "",
            ])

        return output.getvalue()

    # ------------------------------------------------------------------
    # Invalidate
    # ------------------------------------------------------------------

    async def invalidate_voucher(self, db: AsyncSession, voucher_id: uuid.UUID) -> Voucher:
        """Revoke a voucher so it can no longer be redeemed."""
        result = await db.execute(
            select(Voucher).where(Voucher.id == voucher_id)
        )
        voucher = result.scalar_one_or_none()
        if voucher is None:
            raise ValueError("Voucher not found")

        voucher.status = "revoked"
        await db.flush()
        return voucher

    # ------------------------------------------------------------------
    # Redemption history (user-facing)
    # ------------------------------------------------------------------

    async def get_redemption_history(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[VoucherRedemption], int]:
        """Get a user's redemption history."""
        count_q = select(func.count(VoucherRedemption.id)).where(
            VoucherRedemption.user_id == user_id
        )
        total = (await db.execute(count_q)).scalar() or 0

        result = await db.execute(
            select(VoucherRedemption)
            .where(VoucherRedemption.user_id == user_id)
            .order_by(VoucherRedemption.redeemed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        redemptions = list(result.scalars().all())
        return redemptions, total


# Module-level singleton
voucher_service = VoucherService()
