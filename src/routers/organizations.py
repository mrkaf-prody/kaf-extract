"""Organization/Team management endpoints.

POST   /orgs                    — Create organization
GET    /orgs                    — List user's organizations
GET    /orgs/{org_id}           — Get org details
PUT    /orgs/{org_id}           — Update org
DELETE /orgs/{org_id}           — Delete org (owner only)
POST   /orgs/{org_id}/members   — Invite member (by email)
GET    /orgs/{org_id}/members   — List members
PUT    /orgs/{org_id}/members/{user_id}/role — Change member role
DELETE /orgs/{org_id}/members/{user_id} — Remove member
GET    /orgs/{org_id}/usage     — Usage per member
"""

import uuid as _uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import get_current_user
from src.models.sql_models import Organization, OrganizationMember, User

router = APIRouter(tags=["organizations"])


# ── Schemas ────────────────────────────────────────────────────────

class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    billing_email: str | None = None


class UpdateOrgRequest(BaseModel):
    name: str | None = None
    billing_email: str | None = None
    plan: str | None = None


class InviteMemberRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    role: str = Field(default="member", pattern=r"^(admin|member|viewer)$")


class ChangeRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(admin|member|viewer)$")


class MemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    name: str | None
    role: str
    joined_at: str

    @classmethod
    def from_orm(cls, member: OrganizationMember, user: User) -> "MemberResponse":
        return cls(
            id=str(member.id),
            user_id=str(user.id),
            email=user.email,
            name=user.name,
            role=member.role,
            joined_at=member.joined_at.isoformat() if member.joined_at else "",
        )


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    billing_email: str | None
    owner_id: str
    member_count: int = 0
    created_at: str

    @classmethod
    def from_orm(cls, org: Organization, member_count: int = 0) -> "OrgResponse":
        return cls(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            plan=org.plan,
            billing_email=org.billing_email,
            owner_id=str(org.owner_id),
            member_count=member_count,
            created_at=org.created_at.isoformat() if org.created_at else "",
        )


class OrgListResponse(BaseModel):
    organizations: list[OrgResponse]
    total: int


class MemberListResponse(BaseModel):
    members: list[MemberResponse]
    total: int


class UsageItem(BaseModel):
    user_id: str
    email: str
    name: str | None
    role: str
    extraction_count: int = 0


class UsageResponse(BaseModel):
    usage: list[UsageItem]
    total_extractions: int


# ── Helpers ────────────────────────────────────────────────────────

async def _get_org(db: AsyncSession, org_id: str, user_id: str) -> Organization:
    """Fetch org and verify user is a member."""
    org = (
        await db.execute(
            select(Organization).where(Organization.id == _uuid.UUID(org_id))
        )
    ).scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check membership
    member = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org.id,
                OrganizationMember.user_id == _uuid.UUID(user_id),
            )
        )
    ).scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    return org, member


async def _require_admin(member: OrganizationMember):
    """Require admin or owner role."""
    if member.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403, detail="Admin role required for this operation"
        )


async def _require_owner(member: OrganizationMember):
    """Require owner role."""
    if member.role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the organization owner can perform this action"
        )


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from org name."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:100]


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/orgs", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: CreateOrgRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization. The creator becomes the owner."""
    # Check slug uniqueness
    existing = (
        await db.execute(
            select(Organization).where(Organization.slug == body.slug)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Slug '{body.slug}' is already taken. Choose another.",
        )

    user_id = current_user["user_id"]
    org_id = _uuid.uuid4()

    org = Organization(
        id=org_id,
        name=body.name,
        slug=body.slug,
        owner_id=user_id,
        billing_email=body.billing_email,
    )
    db.add(org)

    # Add creator as owner
    member = OrganizationMember(
        id=_uuid.uuid4(),
        org_id=org_id,
        user_id=user_id,
        role="owner",
    )
    db.add(member)
    await db.flush()

    return OrgResponse.from_orm(org, member_count=1)


@router.get("/orgs", response_model=OrgListResponse)
async def list_organizations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all organizations the current user belongs to."""
    user_id = current_user["user_id"]

    # Find all orgs where user is a member
    member_rows = (
        await db.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == user_id)
        )
    ).scalars().all()

    if not member_rows:
        return OrgListResponse(organizations=[], total=0)

    org_ids = [m.org_id for m in member_rows]

    orgs = (
        await db.execute(
            select(Organization).where(Organization.id.in_(org_ids))
        )
    ).scalars().all()

    # Count members per org
    org_count_map = {}
    if org_ids:
        count_rows = (
            await db.execute(
                select(
                    OrganizationMember.org_id,
                    func.count(OrganizationMember.id).label("cnt"),
                )
                .where(OrganizationMember.org_id.in_(org_ids))
                .group_by(OrganizationMember.org_id)
            )
        ).all()
        org_count_map = {row.org_id: row.cnt for row in count_rows}

    return OrgListResponse(
        organizations=[
            OrgResponse.from_orm(org, member_count=org_count_map.get(org.id, 0))
            for org in orgs
        ],
        total=len(orgs),
    )


@router.get("/orgs/{org_id}", response_model=OrgResponse)
async def get_organization(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get organization details."""
    org, member = await _get_org(db, org_id, current_user["user_id"])

    # Count members
    count = (
        await db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.org_id == org.id
            )
        )
    ).scalar() or 0

    return OrgResponse.from_orm(org, member_count=count)


@router.put("/orgs/{org_id}", response_model=OrgResponse)
async def update_organization(
    org_id: str,
    body: UpdateOrgRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update organization settings. Admin or owner only."""
    org, member = await _get_org(db, org_id, current_user["user_id"])
    await _require_admin(member)

    if body.name is not None:
        org.name = body.name
    if body.billing_email is not None:
        org.billing_email = body.billing_email
    if body.plan is not None:
        org.plan = body.plan

    await db.flush()

    count = (
        await db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.org_id == org.id
            )
        )
    ).scalar() or 0

    return OrgResponse.from_orm(org, member_count=count)


@router.delete("/orgs/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an organization. Owner only."""
    org, member = await _get_org(db, org_id, current_user["user_id"])
    await _require_owner(member)

    await db.delete(org)
    await db.flush()


# ── Member Management ──────────────────────────────────────────────

@router.get("/orgs/{org_id}/members", response_model=MemberListResponse)
async def list_members(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all members of an organization."""
    org, member = await _get_org(db, org_id, current_user["user_id"])

    rows = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, OrganizationMember.user_id == User.id)
            .where(OrganizationMember.org_id == org.id)
            .order_by(OrganizationMember.joined_at)
        )
    ).all()

    return MemberListResponse(
        members=[MemberResponse.from_orm(m, u) for m, u in rows],
        total=len(rows),
    )


@router.post("/orgs/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    org_id: str,
    body: InviteMemberRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite a user to the organization by email. Admin or owner only."""
    org, member = await _get_org(db, org_id, current_user["user_id"])
    await _require_admin(member)

    # Find user by email
    invitee = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()

    if not invitee:
        raise HTTPException(
            status_code=404,
            detail=f"User with email '{body.email}' not found. They must register first.",
        )

    # Check if already a member
    existing = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org.id,
                OrganizationMember.user_id == invitee.id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="User is already a member of this organization",
        )

    # Add member
    new_member = OrganizationMember(
        id=_uuid.uuid4(),
        org_id=org.id,
        user_id=invitee.id,
        role=body.role,
        invited_at=datetime.now(UTC),
    )
    db.add(new_member)
    await db.flush()

    return MemberResponse.from_orm(new_member, invitee)


@router.put("/orgs/{org_id}/members/{user_id}/role", response_model=MemberResponse)
async def change_member_role(
    org_id: str,
    user_id: str,
    body: ChangeRoleRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change a member's role. Admin or owner only."""
    org, actor = await _get_org(db, org_id, current_user["user_id"])
    await _require_admin(actor)

    # Can't change owner role
    target = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org.id,
                OrganizationMember.user_id == _uuid.UUID(user_id),
            )
        )
    ).scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    if target.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot change the owner's role")

    # Only owner can promote to admin
    if body.role == "admin" and actor.role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can promote to admin")

    target.role = body.role
    await db.flush()

    # Get user info
    user = (
        await db.execute(select(User).where(User.id == target.user_id))
    ).scalar_one()

    return MemberResponse.from_orm(target, user)


@router.delete("/orgs/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from the organization. Admin or owner only."""
    org, actor = await _get_org(db, org_id, current_user["user_id"])
    await _require_admin(actor)

    target = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org.id,
                OrganizationMember.user_id == _uuid.UUID(user_id),
            )
        )
    ).scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    if target.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove the organization owner")

    # Can't remove yourself unless owner (and there must be another owner)
    if str(target.user_id) == current_user["user_id"] and actor.role != "owner":
        raise HTTPException(status_code=403, detail="Cannot remove yourself")

    await db.delete(target)
    await db.flush()


# ── Usage ──────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/usage", response_model=UsageResponse)
async def org_usage(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get extraction usage per member in the organization."""
    org, member = await _get_org(db, org_id, current_user["user_id"])

    rows = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, OrganizationMember.user_id == User.id)
            .where(OrganizationMember.org_id == org.id)
        )
    ).all()

    usage_items = [
        UsageItem(
            user_id=str(u.id),
            email=u.email,
            name=u.name,
            role=m.role,
            extraction_count=0,  # TODO: track per-user extraction counts
        )
        for m, u in rows
    ]

    return UsageResponse(
        usage=usage_items,
        total_extractions=sum(item.extraction_count for item in usage_items),
    )
