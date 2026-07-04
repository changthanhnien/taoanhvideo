"""VidGen AI — Account model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config.constants import AccountTier


@dataclass
class Account:
    """Google account for Flow API access."""

    id: int = 0
    email: str = ""
    enabled: bool = True
    tier: str = AccountTier.FREE
    credit: int = 0
    proxy: Optional[str] = None
    cookie_path: Optional[str] = None
    cookie_exp: Optional[datetime] = None
    token_exp: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    gemini_api_key: Optional[str] = None
    account_type: str = "google"

    @property
    def display_email(self) -> str:
        """Truncated email for UI display."""
        if len(self.email) > 18:
            return self.email[:15] + "..."
        return self.email

    @property
    def has_credits(self) -> bool:
        return self.credit > 0

    @property
    def is_expired(self) -> bool:
        if not self.cookie_exp:
            return False
        return datetime.now() > self.cookie_exp

    @property
    def is_available(self) -> bool:
        """Account is usable for generation."""
        return self.enabled and not self.is_expired

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "enabled": self.enabled,
            "tier": self.tier,
            "credit": self.credit,
            "proxy": self.proxy,
            "cookie_path": self.cookie_path,
            "cookie_exp": self.cookie_exp.isoformat() if self.cookie_exp else None,
            "token_exp": self.token_exp.isoformat() if self.token_exp else None,
            "created_at": self.created_at.isoformat(),
            "gemini_api_key": self.gemini_api_key,
            "account_type": self.account_type,
        }

    @classmethod
    def from_row(cls, row) -> Account:
        """Create Account from SQLite row."""
        def _parse_dt(val):
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        if hasattr(row, "keys") or isinstance(row, dict):
            return cls(
                id=row["id"],
                email=row["email"],
                enabled=bool(row["enabled"]),
                tier=row["tier"] or AccountTier.FREE,
                credit=row["credit"] or 0,
                proxy=row["proxy"],
                cookie_path=row["cookie_path"],
                cookie_exp=_parse_dt(row["cookie_exp"]),
                token_exp=_parse_dt(row["token_exp"]) if "token_exp" in row.keys() else None,
                created_at=_parse_dt(row["created_at"]) or datetime.now(),
                gemini_api_key=row["gemini_api_key"] if "gemini_api_key" in row.keys() else None,
                account_type=row["account_type"] if "account_type" in row.keys() and row["account_type"] else "google",
            )

        return cls(
            id=row[0],
            email=row[1],
            enabled=bool(row[2]),
            tier=row[3] or AccountTier.FREE,
            credit=row[4] or 0,
            proxy=row[5],
            cookie_path=row[6],
            cookie_exp=_parse_dt(row[7]),
            token_exp=_parse_dt(row[9]) if len(row) > 9 and row[9] else None,
            created_at=_parse_dt(row[8]) or datetime.now(),
            gemini_api_key=row[10] if len(row) > 10 else None,
            account_type=row[11] if len(row) > 11 else "google",
        )
