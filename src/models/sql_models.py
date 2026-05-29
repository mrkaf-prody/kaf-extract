"""SQLAlchemy ORM models for PostgreSQL."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        Enum("admin", "user", name="user_role"), default="user", nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum("active", "suspended", name="user_status"),
        default="active",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    backup_codes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
    trial: Mapped["Trial | None"] = relationship(
        "Trial", back_populates="user", uselist=False,
        cascade="all, delete-orphan", foreign_keys="[Trial.user_id]",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, email={self.email!r})>"


class ApiKey(Base):
    """API key for programmatic access to the extraction endpoints."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    tier: Mapped[str] = mapped_column(
        Enum("hobby", "pro", "enterprise", name="api_key_tier"),
        default="hobby",
        nullable=False,
    )
    rate_limit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("active", "revoked", name="api_key_status"),
        default="active",
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")
    usage_logs: Mapped[list["UsageLog"]] = relationship(
        "UsageLog", back_populates="api_key", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id!r}, label={self.label!r})>"


class RefreshToken(Base):
    """Refresh token for JWT session renewal."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id!r})>"


class UsageLog(Base):
    """Log of API usage per API key."""

    __tablename__ = "usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    api_key: Mapped["ApiKey"] = relationship("ApiKey", back_populates="usage_logs")

    def __repr__(self) -> str:
        return f"<UsageLog(id={self.id!r}, endpoint={self.endpoint!r})>"


# ---------------------------------------------------------------------------
# Phase 4: Payment & Subscription models
# ---------------------------------------------------------------------------

class Subscription(Base):
    """User subscription — maps a user to a plan tier and provider details."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan: Mapped[str] = mapped_column(
        Enum("hobby", "pro", "enterprise", name="subscription_plan"),
        default="hobby",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "active",
            "canceled",
            "expired",
            "past_due",
            "paused",
            name="subscription_status",
        ),
        default="active",
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    provider_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id!r}, plan={self.plan!r}, status={self.status!r})>"


class Trial(Base):
    """Trial period for new users — 7-day, 100 extractions, no credit card."""

    __tablename__ = "trials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Enum("active", "expired", "extended", name="trial_status"),
        default="active",
        nullable=False,
    )
    extractions_total: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    extractions_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reminder_sent_day3: Mapped[bool] = mapped_column(default=False, nullable=False)
    reminder_sent_day6: Mapped[bool] = mapped_column(default=False, nullable=False)
    extended_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    extended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="trial", foreign_keys=[user_id]
    )

    @property
    def extractions_remaining(self) -> int:
        return max(0, self.extractions_total - self.extractions_used)

    def __repr__(self) -> str:
        return (
            f"<Trial(id={self.id!r}, status={self.status!r}, "
            f"remaining={self.extractions_remaining})>"
        )


class Invoice(Base):
    """Generated invoice for a payment."""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    status: Mapped[str] = mapped_column(
        Enum("pending", "paid", "void", "refunded", name="invoice_status"),
        default="pending",
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )
    provider_invoice_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    plan: Mapped[str] = mapped_column(String(50), nullable=False)
    html_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice(id={self.id!r}, amount={self.amount}, "
            f"status={self.status!r})>"
        )


# ---------------------------------------------------------------------------
# Phase 4: Voucher system models
# ---------------------------------------------------------------------------


class Voucher(Base):
    """Promotional voucher code — redeemable for a subscription plan."""

    __tablename__ = "vouchers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    extraction_credits: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Enum("active", "expired", "exhausted", "revoked", name="voucher_status"),
        default="active",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    redemptions: Mapped[list["VoucherRedemption"]] = relationship(
        "VoucherRedemption", back_populates="voucher", cascade="all, delete-orphan"
    )
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by]
    )

    def __repr__(self) -> str:
        return (
            f"<Voucher(id={self.id!r}, code={self.code!r}, "
            f"plan={self.plan!r}, status={self.status!r})>"
        )


class VoucherRedemption(Base):
    """Record of a voucher being redeemed by a user."""

    __tablename__ = "voucher_redemptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vouchers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Relationships
    voucher: Mapped["Voucher"] = relationship(
        "Voucher", back_populates="redemptions"
    )
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<VoucherRedemption(id={self.id!r}, "
            f"voucher_id={self.voucher_id!r}, user_id={self.user_id!r})>"
        )


class ScheduledExtraction(Base):
    """User-defined recurring extraction schedule.

    Supports cron expressions for recurring scraping jobs.
    Tracks last run and next run times. Results delivered via webhook or email.
    """

    __tablename__ = "scheduled_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, doc="Human-readable name for this schedule"
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Standard cron expression (e.g., '0 */6 * * *' for every 6 hours)",
    )
    url: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Target URL to extract"
    )
    schema_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="JSON-serialized extraction schema (fields array)",
    )
    webhook_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Optional webhook to POST results to"
    )
    email_on_complete: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Email to notify on completion"
    )
    status: Mapped[str] = mapped_column(
        Enum("active", "paused", "completed", "error", name="schedule_status"),
        default="active",
        nullable=False,
    )
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Next scheduled run time"
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Last execution timestamp"
    )
    last_job_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, doc="Last arq job ID for status lookup"
    )
    total_runs: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", doc="Total number of executions"
    )
    error_runs: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", doc="Number of failed executions"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<ScheduledExtraction(id={self.id!r}, name={self.name!r}, "
            f"cron={self.cron_expression!r}, status={self.status!r})>"
        )


class Organization(Base):
    """Team/organization account for shared API keys and billing."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan: Mapped[str] = mapped_column(
        String(50), default="hobby", server_default="hobby", nullable=False
    )
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id!r}, name={self.name!r}, slug={self.slug!r})>"


class OrganizationMember(Base):
    """Membership of a user in an organization."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        Enum("owner", "admin", "member", "viewer", name="member_role"),
        default="member",
        server_default="member",
        nullable=False,
    )
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="members"
    )
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<OrganizationMember(org_id={self.org_id!r}, user_id={self.user_id!r}, "
            f"role={self.role!r})>"
        )


class UsageAlert(Base):
    """Per-user usage tracking and alert thresholds."""

    __tablename__ = "usage_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monthly_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    alert_80_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    alert_90_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    alert_100_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    hard_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_usage: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    reset_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<UsageAlert(user_id={self.user_id!r}, usage={self.current_usage}, "
            f"limit={self.monthly_limit}), reset={self.reset_date!r})>"
        )


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """Audit trail for admin actions in the dashboard."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    admin: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<AuditLog(action={self.action!r}, target={self.target_type!r}, "
            f"admin_id={self.admin_id!r})>"
        )


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


class FeatureFlag(Base):
    """Feature flag for gating product features."""

    __tablename__ = "feature_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    requires_plan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<FeatureFlag(key={self.key!r}, enabled={self.default_enabled})>"


class UserFeatureOverride(Base):
    """Per-user override for a feature flag."""

    __tablename__ = "user_feature_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "feature_key", name="uq_user_feature_override"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<UserFeatureOverride(user_id={self.user_id!r}, "
            f"feature_key={self.feature_key!r}, enabled={self.enabled})>"
        )
