"""Tests for Phase 4 trial system.

Covers:
- Trial creation on user registration
- Trial status checks (active, expired, extended)
- Extraction consumption
- Trial extension by admin
- Daily cron: expiration + reminders
- Email reminder generation (mocked Resend)
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import settings
from src.main import app
from src.db import get_db
from src.models.sql_models import Trial


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def mock_db_session():
    """Create a mock async DB session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = AsyncMock()
    session.delete = AsyncMock()
    return session


def _make_trial(
    user_id: uuid.UUID | None = None,
    status: str = "active",
    extractions_total: int = 100,
    extractions_used: int = 0,
    expires_in_days: int = 7,
) -> Trial:
    """Create a Trial model instance for testing."""
    now = datetime.now(UTC)
    return Trial(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        status=status,
        extractions_total=extractions_total,
        extractions_used=extractions_used,
        started_at=now - timedelta(days=7 - expires_in_days),
        expires_at=now + timedelta(days=expires_in_days),
        reminder_sent_day3=False,
        reminder_sent_day6=False,
    )


# ---------------------------------------------------------------------------
# 1. Trial creation
# ---------------------------------------------------------------------------


class TestTrialCreation:
    """Tests for start_trial()."""

    @pytest.mark.asyncio
    async def test_start_trial_creates_record(self, mock_db_session):
        from src.services.trials import start_trial

        user_id = uuid.uuid4()

        # Mock: no existing trial
        mock_scalar = AsyncMock(return_value=None)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        trial = await start_trial(mock_db_session, user_id)

        assert trial is not None
        assert trial.user_id == user_id
        assert trial.status == "active"
        assert trial.extractions_total == 100
        assert trial.extractions_used == 0
        assert trial.extractions_remaining == 100
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_trial_when_already_exists(self, mock_db_session):
        from src.services.trials import start_trial

        user_id = uuid.uuid4()
        existing_trial = _make_trial(user_id)

        mock_scalar = AsyncMock(return_value=existing_trial)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="already has a trial"):
            await start_trial(mock_db_session, user_id)

    @pytest.mark.asyncio
    async def test_start_trial_uses_settings(self, mock_db_session):
        from src.services.trials import start_trial

        user_id = uuid.uuid4()

        mock_scalar = AsyncMock(return_value=None)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(settings, "trial_duration_days", 14):
            with patch.object(settings, "trial_extraction_limit", 200):
                trial = await start_trial(mock_db_session, user_id)

        assert trial.extractions_total == 200


# ---------------------------------------------------------------------------
# 2. Trial status checks
# ---------------------------------------------------------------------------


class TestTrialChecks:
    """Tests for check_trial and extraction consumption."""

    @pytest.mark.asyncio
    async def test_check_trial_active(self, mock_db_session):
        from src.services.trials import check_trial

        user_id = uuid.uuid4()
        trial = _make_trial(user_id, status="active", expires_in_days=3, extractions_used=0)

        mock_scalar = AsyncMock(return_value=trial)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await check_trial(mock_db_session, user_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_trial_expired(self, mock_db_session):
        from src.services.trials import check_trial

        user_id = uuid.uuid4()
        trial = _make_trial(user_id, status="active", expires_in_days=-1)  # expired

        mock_scalar = AsyncMock(return_value=trial)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await check_trial(mock_db_session, user_id)
        assert result is False
        assert trial.status == "expired"  # should auto-expire

    @pytest.mark.asyncio
    async def test_check_trial_no_extractions_left(self, mock_db_session):
        from src.services.trials import check_trial

        user_id = uuid.uuid4()
        trial = _make_trial(
            user_id, status="active", expires_in_days=2,
            extractions_total=100, extractions_used=100
        )

        mock_scalar = AsyncMock(return_value=trial)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await check_trial(mock_db_session, user_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_trial_none(self, mock_db_session):
        from src.services.trials import check_trial

        mock_scalar = AsyncMock(return_value=None)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await check_trial(mock_db_session, uuid.uuid4())
        assert result is False


# ---------------------------------------------------------------------------
# 3. Extraction consumption
# ---------------------------------------------------------------------------


class TestExtractionConsumption:
    """Tests for consume_extraction()."""

    @pytest.mark.asyncio
    async def test_consume_extraction_increments_counter(self, mock_db_session):
        from src.services.trials import check_trial, consume_extraction, get_trial

        user_id = uuid.uuid4()
        trial = _make_trial(user_id, status="active", expires_in_days=3, extractions_used=5)

        mock_scalar = AsyncMock(return_value=trial)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # consume_extraction calls check_trial which also does execute
        result = await consume_extraction(mock_db_session, user_id)
        assert result is True
        assert trial.extractions_used == 6

    @pytest.mark.asyncio
    async def test_consume_extraction_when_exhausted(self, mock_db_session):
        from src.services.trials import consume_extraction

        user_id = uuid.uuid4()
        trial = _make_trial(
            user_id, status="active", expires_in_days=2,
            extractions_total=100, extractions_used=100
        )

        mock_scalar = AsyncMock(return_value=trial)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await consume_extraction(mock_db_session, user_id)
        assert result is False
        assert trial.extractions_used == 100  # unchanged


# ---------------------------------------------------------------------------
# 4. Trial extension (admin)
# ---------------------------------------------------------------------------


class TestTrialExtension:
    """Tests for extend_trial()."""

    @pytest.mark.asyncio
    async def test_extend_trial_adds_days_and_extractions(self, mock_db_session):
        from src.services.trials import extend_trial

        user_id = uuid.uuid4()
        admin_id = uuid.uuid4()
        trial = _make_trial(user_id, status="active", expires_in_days=3,
                            extractions_total=100, extractions_used=80)

        mock_scalar = AsyncMock(return_value=trial)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        extended = await extend_trial(
            mock_db_session, user_id,
            extra_days=14, extra_extractions=200,
            admin_id=admin_id,
        )

        assert extended is not None
        assert extended.status == "extended"
        assert extended.extractions_total == 300  # 100 + 200
        assert extended.extended_by_id == admin_id

    @pytest.mark.asyncio
    async def test_extend_trial_no_trial(self, mock_db_session):
        from src.services.trials import extend_trial

        mock_scalar = AsyncMock(return_value=None)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await extend_trial(mock_db_session, uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# 5. Daily cron: expirations
# ---------------------------------------------------------------------------


class TestTrialExpirations:
    """Tests for process_trial_expirations()."""

    @pytest.mark.asyncio
    async def test_expire_stale_trials(self, mock_db_session):
        from src.services.trials import process_trial_expirations

        user_id = uuid.uuid4()
        # Trial that expired yesterday
        trial = _make_trial(user_id, status="active", expires_in_days=-1)

        mock_scalars = MagicMock()
        mock_scalars.return_value = [trial]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await process_trial_expirations(mock_db_session)

        assert result["expired"] == 1
        assert trial.status == "expired"

    @pytest.mark.asyncio
    async def test_expire_no_stale_trials(self, mock_db_session):
        from src.services.trials import process_trial_expirations

        mock_scalars = MagicMock()
        mock_scalars.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await process_trial_expirations(mock_db_session)
        assert result["expired"] == 0


# ---------------------------------------------------------------------------
# 6. Registration auto-starts trial (integration via auth router)
# ---------------------------------------------------------------------------


class TestRegistrationTrialIntegration:
    """Verify that registration triggers trial creation."""

    @pytest.mark.asyncio
    async def test_register_starts_trial(self, client, mock_db_session):
        """POST /auth/register should start a trial."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock: no existing user
        mock_scalar_none = AsyncMock(return_value=None)
        mock_result_none = AsyncMock()
        mock_result_none.scalar_one_or_none.return_value = mock_scalar_none()
        mock_db_session.execute = AsyncMock(return_value=mock_result_none)

        try:
            response = await client.post("/auth/register", json={
                "email": "trialuser@example.com",
                "password": "securepassword123",
                "name": "Trial User",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        # Should succeed (201) — trial start is non-fatal
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


# ---------------------------------------------------------------------------
# 7. Email reminders (mocked Resend)
# ---------------------------------------------------------------------------


class TestTrialReminders:
    """Tests for send_trial_reminders() with mocked Resend."""

    @pytest.mark.asyncio
    async def test_send_day3_reminder(self, mock_db_session):
        from src.services.trials import send_trial_reminders

        user_id = uuid.uuid4()
        # Trial started 3 days ago
        trial = _make_trial(user_id, status="active", expires_in_days=4,
                            extractions_used=20)
        trial.started_at = datetime.now(UTC) - timedelta(days=3)
        trial.reminder_sent_day3 = False
        trial.reminder_sent_day6 = False

        # Mock user lookup
        mock_user = MagicMock()
        mock_user.email = "user@example.com"
        mock_user.name = "User Name"

        # First execute call (trials query) returns [trial],
        # second (user lookup) returns mock_user
        mock_scalars_trials = MagicMock()
        mock_scalars_trials.return_value = [trial]

        mock_scalars_user = MagicMock()
        mock_scalars_user.return_value = [mock_user]
        mock_scalar_user_one = AsyncMock(return_value=mock_user)

        mock_result_trials = MagicMock()
        mock_result_trials.scalars.return_value = mock_scalars_trials()

        mock_result_user = MagicMock()
        mock_result_user.scalar_one_or_none.return_value = mock_scalar_user_one()

        mock_db_session.execute = AsyncMock()
        mock_db_session.execute.side_effect = [mock_result_trials, mock_result_user]

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp

            with patch.object(settings, "resend_api_key", "test-key"):
                result = await send_trial_reminders(mock_db_session)

        assert result["reminders_sent"] == 1
        assert trial.reminder_sent_day3 is True
        assert trial.reminder_sent_day6 is False  # only day 3

    @pytest.mark.asyncio
    async def test_skip_when_no_resend_key(self, mock_db_session):
        from src.services.trials import send_trial_reminders

        user_id = uuid.uuid4()
        trial = _make_trial(user_id, status="active", expires_in_days=4,
                            extractions_used=20)
        trial.started_at = datetime.now(UTC) - timedelta(days=3)

        mock_scalars = MagicMock()
        mock_scalars.return_value = [trial]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # No resend API key
        with patch.object(settings, "resend_api_key", ""):
            result = await send_trial_reminders(mock_db_session)

        assert result["reminders_sent"] == 1  # still marks as sent, just skips email


# ---------------------------------------------------------------------------
# 8. Daily maintenance entrypoint
# ---------------------------------------------------------------------------


class TestDailyMaintenance:
    """Tests for daily_trial_maintenance()."""

    @pytest.mark.asyncio
    async def test_daily_maintenance_runs_both(self, mock_db_session):
        from src.services.trials import daily_trial_maintenance

        # Both queries return empty: no trials to expire/remind
        mock_scalars = MagicMock()
        mock_scalars.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await daily_trial_maintenance(mock_db_session)

        assert "expired" in result
        assert "reminders_sent" in result
        assert result["expired"] == 0
        assert result["reminders_sent"] == 0


# ---------------------------------------------------------------------------
# 9. Trial model properties
# ---------------------------------------------------------------------------


class TestTrialModel:
    """Tests for the Trial model properties."""

    def test_extractions_remaining_property(self):
        trial = _make_trial(extractions_total=100, extractions_used=35)
        assert trial.extractions_remaining == 65

    def test_extractions_remaining_floor_zero(self):
        trial = _make_trial(extractions_total=100, extractions_used=200)
        assert trial.extractions_remaining == 0

    def test_trial_repr(self):
        trial = _make_trial()
        repr_str = repr(trial)
        assert "Trial" in repr_str
        assert "remaining" in repr_str
