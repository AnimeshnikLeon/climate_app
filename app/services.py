import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import date
from typing import Iterable
from typing import Optional

from sqlalchemy.orm import Session

from . import models


ROLE_MANAGER = "Менеджер"
ROLE_SPECIALIST = "Специалист"
ROLE_OPERATOR = "Оператор"
ROLE_CLIENT = "Заказчик"

DEFAULT_PBKDF2_ITERATIONS = 120_000


@dataclass(frozen=True)
class request_row:
    start_date: date
    completion_date: Optional[date]
    status_is_final: bool
    equipment_type: str
    issue_type: str


def hash_password(password: str, iterations: int = DEFAULT_PBKDF2_ITERATIONS) -> str:
    if password is None:
        raise ValueError("Password is required")

    password_clean = str(password)
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password_clean.encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )

    salt_b64 = base64.b64encode(salt).decode("ascii")
    dk_b64 = base64.b64encode(dk).decode("ascii")
    return f"pbkdf2_sha256${iterations}${salt_b64}${dk_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not password:
        return False
    if not stored_hash:
        return False

    parts = stored_hash.split("$")
    if len(parts) != 4:
        return False
    if parts[0] != "pbkdf2_sha256":
        return False

    try:
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("ascii"))
        expected = base64.b64decode(parts[3].encode("ascii"))
    except (ValueError, OSError):
        return False

    dk = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected),
    )
    return hmac.compare_digest(dk, expected)


def authenticate_user(db: Session, login: str, password: str) -> Optional[models.User]:
    login_clean = (login or "").strip()
    if not login_clean:
        return None

    user = db.query(models.User).filter(models.User.login == login_clean).first()
    if not user:
        return None

    if not verify_password(password=password, stored_hash=user.password_hash):
        return None

    return user


def ensure_default_secret_key() -> str:
    env_key = os.getenv("APP_SECRET_KEY")
    if env_key:
        return env_key
    return secrets.token_urlsafe(32)


def normalize_issue_type_name(problem_description: str) -> str:
    text = (problem_description or "").strip()
    if not text:
        return "Не указано"
    if len(text) <= 255:
        return text
    return text[:252].rstrip() + "..."


def calculate_statistics_from_rows(rows: Iterable[request_row]) -> dict:
    total_requests = 0
    completed_requests = 0

    durations_days: list[int] = []
    by_equipment_type: dict[str, int] = {}
    by_issue_type: dict[str, int] = {}

    for r in rows:
        total_requests += 1

        equip = (r.equipment_type or "").strip() or "Не указано"
        by_equipment_type[equip] = by_equipment_type.get(equip, 0) + 1

        issue = (r.issue_type or "").strip() or "Не указано"
        by_issue_type[issue] = by_issue_type.get(issue, 0) + 1

        if r.status_is_final and r.completion_date is not None:
            completed_requests += 1
            delta = (r.completion_date - r.start_date).days
            if delta < 0:
                continue
            durations_days.append(delta)

    average_repair_time_days: Optional[float]
    if durations_days:
        average_repair_time_days = sum(durations_days) / len(durations_days)
    else:
        average_repair_time_days = None

    return {
        "total_requests": total_requests,
        "completed_requests": completed_requests,
        "average_repair_time_days": average_repair_time_days,
        "by_equipment_type": dict(sorted(by_equipment_type.items(), key=lambda x: (-x[1], x[0]))),
        "by_issue_type": dict(sorted(by_issue_type.items(), key=lambda x: (-x[1], x[0]))),
    }


def calculate_statistics(db: Session) -> dict:
    requests = (
        db.query(models.RepairRequest)
        .join(models.EquipmentModel, models.RepairRequest.equipment_model_id == models.EquipmentModel.id)
        .join(models.EquipmentType, models.EquipmentModel.equipment_type_id == models.EquipmentType.id)
        .join(models.IssueType, models.RepairRequest.issue_type_id == models.IssueType.id)
        .join(models.RequestStatus, models.RepairRequest.status_id == models.RequestStatus.id)
        .all()
    )

    rows: list[request_row] = []
    for req in requests:
        rows.append(
            request_row(
                start_date=req.start_date,
                completion_date=req.completion_date,
                status_is_final=bool(req.status.is_final),
                equipment_type=req.equipment_model.equipment_type.name,
                issue_type=req.issue_type.name,
            )
        )

    return calculate_statistics_from_rows(rows)