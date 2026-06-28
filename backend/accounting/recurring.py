"""Recurring / scheduled transaction rules for TaxFlow Pro v3.11."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from backend.models import RecurringRule as RecurringRuleModel


@dataclass
class RecurringRule:
    """Lightweight domain model for a recurring rule."""

    id: int | None = None
    account_id: int = 0
    tenant_id: int = 0
    user_id: int = 0
    amount: Decimal = Decimal("0.00")
    description: str = ""
    frequency: str = "monthly"  # daily/weekly/monthly/yearly
    start_date: date = field(default_factory=date.today)
    end_date: date | None = None
    count: int | None = None
    splits_json: str = "[]"
    next_date: date | None = None
    is_active: bool = True

    @property
    def splits(self) -> list[dict]:
        try:
            data = json.loads(self.splits_json or "[]")
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @splits.setter
    def splits(self, value: list[dict] | None) -> None:
        self.splits_json = json.dumps(value or [])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "amount": float(self.amount),
            "description": self.description,
            "frequency": self.frequency,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "count": self.count,
            "splits_json": self.splits_json,
            "splits": self.splits,
            "next_date": self.next_date.isoformat() if self.next_date else None,
            "is_active": self.is_active,
        }


ALLOWED_FREQUENCIES = {"daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"}


def _frequency_to_days(freq: str) -> int:
    return {
        "daily": 1,
        "weekly": 7,
        "biweekly": 14,
        "monthly": 30,
        "quarterly": 90,
        "yearly": 365,
    }.get(freq, 30)


def _advance_date(current: date, frequency: str) -> date:
    from datetime import timedelta
    if frequency == "daily":
        return current + timedelta(days=1)
    if frequency == "weekly":
        return current + timedelta(weeks=1)
    if frequency == "biweekly":
        return current + timedelta(weeks=2)
    if frequency == "monthly":
        day = current.day
        if current.month == 12:
            next_date = date(current.year + 1, 1, day)
        else:
            try:
                next_date = date(current.year, current.month + 1, day)
            except ValueError:
                # End of month shorter than current day: clamp to month end.
                first_next = date(current.year, current.month + 1, 1)
                next_date = date(first_next.year, first_next.month, 1) + timedelta(days=32)
                next_date = next_date.replace(day=1) - timedelta(days=1)
        return next_date
    if frequency == "quarterly":
        # Advance 3 months.
        day = current.day
        new_month = current.month + 3
        new_year = current.year
        while new_month > 12:
            new_month -= 12
            new_year += 1
        try:
            return date(new_year, new_month, day)
        except ValueError:
            # Clamp to month end.
            import calendar
            last_day = calendar.monthrange(new_year, new_month)[1]
            return date(new_year, new_month, last_day)
    if frequency == "yearly":
        return date(current.year + 1, current.month, current.day)
    return current + timedelta(days=_frequency_to_days(frequency))


def generate_upcoming(rule: RecurringRule, count: int = 5) -> list[date]:
    """Generate the next ``count`` scheduled dates for a rule."""
    if not rule.is_active:
        return []
    start = rule.next_date or rule.start_date
    if start is None:
        return []
    results = []
    current = start
    max_count = rule.count
    generated = 0
    while len(results) < count:
        if rule.end_date and current > rule.end_date:
            break
        if max_count is not None and generated >= max_count:
            break
        results.append(current)
        current = _advance_date(current, rule.frequency)
        generated += 1
    return results


def generate_occurrences(
    db: "Session",
    rule_id: int,
    target_date: date,
    tenant_id: int | None = None,
    user_id: int | None = None,
) -> list[dict]:
    """Generate pending occurrences for a recurring rule up to ``target_date``.

    This is IDEMPOTENT: calling it twice with the same target_date produces
    no duplicate occurrences. It checks for existing transactions with
    ``txn_uid`` matching ``recurring:{rule_id}:{date}`` to avoid duplicates.

    Returns a list of occurrence dicts with scheduled_date and status="pending".
    Does NOT create real transactions — use ``materialize_rule`` for that.
    """
    from backend import models

    rule = db.query(models.RecurringRule).filter(models.RecurringRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    if tenant_id is not None and rule.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    if user_id is not None and rule.user_id != user_id:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    if not rule.is_active:
        return []

    domain_rule = _model_to_domain(rule)
    upcoming = generate_upcoming(domain_rule, count=999)

    # Filter to dates <= target_date.
    due = [d for d in upcoming if d <= target_date]

    # Check which occurrences already exist (idempotency).
    existing_uids = set()
    if due:
        uids = [f"recurring:{rule.id}:{d.isoformat()}" for d in due]
        existing = (
            db.query(models.Transaction.txn_uid)
            .filter(models.Transaction.txn_uid.in_(uids))
            .all()
        )
        existing_uids = {row[0] for row in existing}

    occurrences = []
    for scheduled in due:
        uid = f"recurring:{rule.id}:{scheduled.isoformat()}"
        if uid in existing_uids:
            continue  # Already generated — idempotent skip.
        occurrences.append({
            "scheduled_date": scheduled.isoformat(),
            "description": rule.description,
            "amount": float(rule.amount) if rule.amount is not None else 0.0,
            "status": "pending",
            "rule_id": rule.id,
        })

    return occurrences


def materialize_rule(
    db: "Session",
    rule_id: int,
    as_of_date: date | None = None,
    current_user: object | None = None,
) -> list[dict]:
    """Materialize real transaction(s) from a recurring rule as of a date.

    In v3.11 the recurring engine creates lightweight register entries that
    reference the originating account.  Only dates up to ``as_of_date`` are
    materialized; the rule's ``next_date`` is advanced so future checks
    create new instances.
    """
    from backend import models

    rule = db.query(models.RecurringRule).filter(models.RecurringRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    if not rule.is_active:
        raise HTTPException(status_code=400, detail="Rule is inactive")

    effective_date = as_of_date or date.today()
    if rule.next_date is None:
        rule.next_date = rule.start_date
    upcoming = generate_upcoming(_model_to_domain(rule), count=rule.count or 5)

    created = []
    for scheduled in upcoming:
        if scheduled > effective_date:
            break
        # Find or create a synthetic statement for this account so the
        # v3.10 Transaction model's ``statement_id`` FK is satisfied.
        statement = (
            db.query(models.Statement)
            .filter(
                models.Statement.account_id == rule.account_id,
                models.Statement.tenant_id == rule.tenant_id,
                models.Statement.user_id == rule.user_id,
                models.Statement.filename == "__recurring__",
            )
            .first()
        )
        if statement is None:
            statement = models.Statement(
                account_id=rule.account_id,
                tenant_id=rule.tenant_id,
                user_id=rule.user_id,
                filename="__recurring__",
                period_start=rule.start_date,
                period_end=effective_date,
                opening_balance=Decimal("0.00"),
                closing_balance=Decimal("0.00"),
                variance=Decimal("0.00"),
            )
            db.add(statement)
            db.flush()

        txn = models.Transaction(
            statement_id=statement.id,
            tenant_id=rule.tenant_id,
            user_id=rule.user_id,
            date=scheduled,
            description=rule.description,
            amount=rule.amount,
            tx_type="recurring",
            category="recurring",
            txn_uid=f"recurring:{rule.id}:{scheduled.isoformat()}",
            import_source="recurring",
        )
        db.add(txn)
        created.append(txn)
        rule.next_date = _advance_date(scheduled, rule.frequency)
        if rule.count is not None:
            rule.count = max(0, rule.count - 1)

    db.commit()
    for txn in created:
        db.refresh(txn)

    return [t.to_dict() for t in created]


def _model_to_domain(rule: "RecurringRuleModel") -> RecurringRule:
    return RecurringRule(
        id=rule.id,
        account_id=rule.account_id,
        tenant_id=rule.tenant_id,
        user_id=rule.user_id,
        amount=Decimal(rule.amount) if rule.amount is not None else Decimal("0.00"),
        description=rule.description or "",
        frequency=rule.frequency,
        start_date=rule.start_date,
        end_date=rule.end_date,
        count=rule.count,
        splits_json=rule.splits_json or "[]",
        next_date=rule.next_date,
        is_active=rule.is_active,
    )


def _domain_to_model(rule: RecurringRule, model: "RecurringRuleModel") -> None:
    model.account_id = rule.account_id
    model.tenant_id = rule.tenant_id
    model.user_id = rule.user_id
    model.amount = rule.amount
    model.description = rule.description
    model.frequency = rule.frequency
    model.start_date = rule.start_date
    model.end_date = rule.end_date
    model.count = rule.count
    model.splits_json = rule.splits_json
    model.next_date = rule.next_date
    model.is_active = rule.is_active


def create_rule(
    db: "Session",
    tenant_id: int,
    user_id: int,
    account_id: int,
    description: str,
    amount: Decimal | float | str,
    frequency: str,
    start_date: date,
    end_date: date | None = None,
    count: int | None = None,
    splits: list[dict] | None = None,
    is_active: bool = True,
) -> RecurringRule:
    from backend import models

    frequency = frequency.lower().strip()
    if frequency not in ALLOWED_FREQUENCIES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid frequency '{frequency}'. Must be one of: {', '.join(sorted(ALLOWED_FREQUENCIES))}",
        )

    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))
    elif isinstance(amount, str):
        amount = Decimal(amount)

    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")

    # Validate referenced account exists.
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.tenant_id == tenant_id,
        models.Account.user_id == user_id,
    ).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    rule = RecurringRule(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=user_id,
        amount=amount,
        description=description.strip(),
        frequency=frequency,
        start_date=start_date,
        end_date=end_date,
        count=count,
        next_date=start_date,
        is_active=is_active,
    )
    if splits:
        rule.splits = splits

    model = models.RecurringRule()
    _domain_to_model(rule, model)
    db.add(model)
    db.commit()
    db.refresh(model)
    return _model_to_domain(model)


def list_rules(db: "Session", tenant_id: int, user_id: int | None = None) -> list[RecurringRule]:
    from backend import models

    query = db.query(models.RecurringRule).filter(models.RecurringRule.tenant_id == tenant_id)
    if user_id is not None:
        query = query.filter(models.RecurringRule.user_id == user_id)
    return [_model_to_domain(r) for r in query.order_by(models.RecurringRule.id.desc()).all()]


def get_rule(db: "Session", rule_id: int, tenant_id: int, user_id: int | None = None) -> RecurringRule | None:
    from backend import models

    query = db.query(models.RecurringRule).filter(
        models.RecurringRule.id == rule_id,
        models.RecurringRule.tenant_id == tenant_id,
    )
    if user_id is not None:
        query = query.filter(models.RecurringRule.user_id == user_id)
    row = query.first()
    return _model_to_domain(row) if row else None


def update_rule(
    db: "Session",
    rule_id: int,
    tenant_id: int,
    user_id: int,
    **updates,
) -> RecurringRule:
    from backend import models

    row = (
        db.query(models.RecurringRule)
        .filter(
            models.RecurringRule.id == rule_id,
            models.RecurringRule.tenant_id == tenant_id,
            models.RecurringRule.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")

    domain = _model_to_domain(row)
    if "description" in updates and updates["description"] is not None:
        domain.description = updates["description"].strip()
    if "amount" in updates and updates["amount"] is not None:
        amount = updates["amount"]
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        elif isinstance(amount, str):
            amount = Decimal(amount)
        domain.amount = amount
    if "frequency" in updates and updates["frequency"] is not None:
        freq = updates["frequency"].lower().strip()
        if freq not in ALLOWED_FREQUENCIES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid frequency '{freq}'. Must be one of: {', '.join(sorted(ALLOWED_FREQUENCIES))}",
            )
        domain.frequency = freq
    if "start_date" in updates and updates["start_date"] is not None:
        domain.start_date = updates["start_date"]
        if domain.next_date is None or domain.next_date < domain.start_date:
            domain.next_date = domain.start_date
    if "end_date" in updates:
        domain.end_date = updates["end_date"]
    if "count" in updates and updates["count"] is not None:
        domain.count = updates["count"]
    if "splits" in updates and updates["splits"] is not None:
        domain.splits = updates["splits"]
    if "is_active" in updates and updates["is_active"] is not None:
        domain.is_active = bool(updates["is_active"])

    if domain.end_date and domain.start_date and domain.end_date < domain.start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")

    _domain_to_model(domain, row)
    db.commit()
    db.refresh(row)
    return _model_to_domain(row)


def delete_rule(db: "Session", rule_id: int, tenant_id: int, user_id: int) -> None:
    from backend import models

    row = (
        db.query(models.RecurringRule)
        .filter(
            models.RecurringRule.id == rule_id,
            models.RecurringRule.tenant_id == tenant_id,
            models.RecurringRule.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    db.delete(row)
    db.commit()
