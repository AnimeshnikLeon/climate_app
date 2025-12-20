from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

ROLE_MANAGER = "Менеджер"
ROLE_SPECIALIST = "Специалист"
ROLE_OPERATOR = "Оператор"
ROLE_CLIENT = "Заказчик"
ROLE_QUALITY_MANAGER = "Менеджер по качеству"

DEFAULT_PBKDF2_ITERATIONS = 120_000

QUALITY_SURVEY_BASE_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSdhZcExx6LSIXxk0ub55mSu-WIh23WYdGG9HY5EZhLDo7P8eA/viewform?usp=sf_link"
)


@dataclass(frozen=True)
class RequestRow:
    """
    Плоское представление строки заявки для расчёта статистики.
    Используется как DTO поверх ORM-моделей.
    """

    start_date: date
    completion_date: Optional[date]
    status_is_final: bool
    equipment_type: str
    issue_type: str


@dataclass(frozen=True)
class ReferenceLookups:
    """
    Набор справочников, общих для списка и форм заявок.
    """

    statuses: list[models.RequestStatus]
    equipment_types: list[models.EquipmentType]
    issue_types: list[models.IssueType]


@dataclass(frozen=True)
class RequestFormLookups(ReferenceLookups):
    """
    Расширенный набор данных для форм создания/редактирования заявок.
    """

    specialists: list[models.User]
    clients: list[models.User]


def hash_password(
    password: str,
    iterations: int = DEFAULT_PBKDF2_ITERATIONS,
) -> str:
    """
    Хэширование пароля с использованием PBKDF2-HMAC-SHA256.

    Формат результата:
    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
    """
    if password is None:
        raise ValueError("Password is required")

    password_clean = str(password)
    if not password_clean:
        raise ValueError("Password must not be empty")

    salt = secrets.token_bytes(16)

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password_clean.encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )

    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(derived_key).decode("ascii")

    return f"pbkdf2_sha256${iterations}${salt_b64}${hash_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Проверка пароля против сохранённого PBKDF2-хэша.
    Возвращает False при любом формате хэша, отличном от ожидаемого.
    """
    if not password or not stored_hash:
        return False

    parts = stored_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False

    try:
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("ascii"))
        expected = base64.b64decode(parts[3].encode("ascii"))
    except (ValueError, OSError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected),
    )

    return hmac.compare_digest(candidate, expected)


def authenticate_user(
    db: Session,
    login: str,
    password: str,
) -> Optional[models.User]:
    """
    Аутентификация пользователя по логину и паролю.
    При неуспехе возвращает None, не раскрывая, что именно не так.
    """
    login_clean = (login or "").strip()
    if not login_clean:
        return None

    user = (
        db.query(models.User)
        .filter(models.User.login == login_clean)
        .first()
    )
    if not user:
        return None

    if not verify_password(password=password, stored_hash=user.password_hash):
        return None

    return user


def ensure_default_secret_key() -> str:
    """
    Возвращает секретный ключ приложения.
    В проде ключ должен приходить из окружения (APP_SECRET_KEY),
    генерация случайного ключа уместна только для локальной отладки.
    """
    env_key = os.getenv("APP_SECRET_KEY")
    if env_key:
        return env_key

    return secrets.token_urlsafe(32)


def normalize_issue_type_name(problem_description: str) -> str:
    """
    Нормализация текста описания проблемы до значения справочника IssueType.

    - пустая строка → «Не указано»;
    - длина обрезается до 255 символов с многоточием.
    """
    text = (problem_description or "").strip()
    if not text:
        return "Не указано"

    if len(text) <= 255:
        return text

    return text[:252].rstrip() + "..."


def calculate_statistics_from_rows(
    rows: Iterable[RequestRow],
) -> dict[str, Any]:
    """
    Расчёт агрегированной статистики по заранее подготовленному набору строк.

    Возвращает словарь:
    - total_requests: int
    - completed_requests: int
    - average_repair_time_days: Optional[float]
    - by_equipment_type: dict[str, int]
    - by_issue_type: dict[str, int]
    """
    total_requests = 0
    completed_requests = 0

    durations_days: list[int] = []
    by_equipment_type: dict[str, int] = {}
    by_issue_type: dict[str, int] = {}

    for r in rows:
        total_requests += 1

        equipment_name = (r.equipment_type or "").strip() or "Не указано"
        by_equipment_type[equipment_name] = (
            by_equipment_type.get(equipment_name, 0) + 1
        )

        issue_name = (r.issue_type or "").strip() or "Не указано"
        by_issue_type[issue_name] = by_issue_type.get(issue_name, 0) + 1

        if r.status_is_final and r.completion_date is not None:
            completed_requests += 1
            delta = (r.completion_date - r.start_date).days
            if delta < 0:
                continue
            durations_days.append(delta)

    if durations_days:
        average_repair_time_days: Optional[float] = (
            sum(durations_days) / len(durations_days)
        )
    else:
        average_repair_time_days = None

    return {
        "total_requests": total_requests,
        "completed_requests": completed_requests,
        "average_repair_time_days": average_repair_time_days,
        "by_equipment_type": dict(
            sorted(
                by_equipment_type.items(),
                key=lambda item: (-item[1], item[0]),
            ),
        ),
        "by_issue_type": dict(
            sorted(
                by_issue_type.items(),
                key=lambda item: (-item[1], item[0]),
            ),
        ),
    }


def calculate_specialist_load(db: Session) -> list[dict[str, Any]]:
    """
    Нагрузка специалистов: количество активных (не финальных) заявок
    на каждого специалиста.
    """
    rows = (
        db.query(
            models.User.id,
            models.User.fio,
            func.count(models.RepairRequest.id),
        )
        .join(models.UserRole, models.User.role_id == models.UserRole.id)
        .join(
            models.RepairRequest,
            models.RepairRequest.master_id == models.User.id,
        )
        .join(
            models.RequestStatus,
            models.RepairRequest.status_id == models.RequestStatus.id,
        )
        .filter(models.UserRole.name == ROLE_SPECIALIST)
        .filter(models.RequestStatus.is_final.is_(False))
        .group_by(models.User.id, models.User.fio)
        .order_by(func.count(models.RepairRequest.id).desc(), models.User.fio)
        .all()
    )

    result: list[dict[str, Any]] = []
    for user_id, fio, active_count in rows:
        result.append(
            {
                "master_id": int(user_id),
                "master_fio": fio,
                "active_requests": int(active_count),
            }
        )

    return result


def calculate_statistics(db: Session) -> dict[str, Any]:
    """
    Расчёт статистики по всем заявкам в базе:
    базовые агрегаты + нагрузка специалистов.
    """
    requests = (
        db.query(models.RepairRequest)
        .join(
            models.EquipmentModel,
            models.RepairRequest.equipment_model_id
            == models.EquipmentModel.id,
        )
        .join(
            models.EquipmentType,
            models.EquipmentModel.equipment_type_id
            == models.EquipmentType.id,
        )
        .join(
            models.IssueType,
            models.RepairRequest.issue_type_id == models.IssueType.id,
        )
        .join(
            models.RequestStatus,
            models.RepairRequest.status_id == models.RequestStatus.id,
        )
        .all()
    )

    rows: list[RequestRow] = []
    for req in requests:
        rows.append(
            RequestRow(
                start_date=req.start_date,
                completion_date=req.completion_date,
                status_is_final=bool(req.status.is_final),
                equipment_type=req.equipment_model.equipment_type.name,
                issue_type=req.issue_type.name,
            )
        )

    stats = calculate_statistics_from_rows(rows)
    stats["specialist_load"] = calculate_specialist_load(db)

    return stats


def get_or_create_equipment_model(
    db: Session,
    equipment_type_id: int,
    model_name: str,
) -> models.EquipmentModel:
    """
    Находит модель оборудования по типу и названию или создаёт новую.
    """
    cleaned_name = (model_name or "").strip()

    existing = (
        db.query(models.EquipmentModel)
        .filter(models.EquipmentModel.equipment_type_id == equipment_type_id)
        .filter(models.EquipmentModel.name == cleaned_name)
        .first()
    )
    if existing:
        return existing

    created = models.EquipmentModel(
        equipment_type_id=equipment_type_id,
        name=cleaned_name,
    )
    db.add(created)
    db.flush()

    return created


def get_or_create_issue_type(
    db: Session,
    problem_description: str,
) -> models.IssueType:
    """
    Находит тип неисправности по нормализованному названию или создаёт новый.
    """
    name = normalize_issue_type_name(problem_description)

    existing = (
        db.query(models.IssueType)
        .filter(models.IssueType.name == name)
        .first()
    )
    if existing:
        return existing

    created = models.IssueType(name=name)
    db.add(created)
    db.flush()

    return created


def load_reference_lookups(db: Session) -> ReferenceLookups:
    """
    Справочные данные для фильтров и форм:
    статусы, типы оборудования, типы неисправностей.
    """
    statuses = (
        db.query(models.RequestStatus)
        .order_by(models.RequestStatus.name)
        .all()
    )
    equipment_types = (
        db.query(models.EquipmentType)
        .order_by(models.EquipmentType.name)
        .all()
    )
    issue_types = (
        db.query(models.IssueType)
        .order_by(models.IssueType.name)
        .all()
    )

    return ReferenceLookups(
        statuses=statuses,
        equipment_types=equipment_types,
        issue_types=issue_types,
    )


def load_request_form_lookups(db: Session) -> RequestFormLookups:
    """
    Полный набор данных для форм создания/редактирования заявок.
    """
    base = load_reference_lookups(db)

    specialists = (
        db.query(models.User)
        .join(models.UserRole)
        .filter(models.UserRole.name == ROLE_SPECIALIST)
        .order_by(models.User.fio)
        .all()
    )

    clients = (
        db.query(models.User)
        .join(models.UserRole)
        .filter(models.UserRole.name == ROLE_CLIENT)
        .order_by(models.User.fio)
        .all()
    )

    return RequestFormLookups(
        statuses=base.statuses,
        equipment_types=base.equipment_types,
        issue_types=base.issue_types,
        specialists=specialists,
        clients=clients,
    )


def get_new_request_status(db: Session) -> models.RequestStatus:
    """
    Возвращает статус, используемый по умолчанию для новой заявки.

    Предпочтительно статус с названием «Новая заявка».
    Если он отсутствует, берётся первый не финальный статус по id.
    Если и таких нет — выбрасывается исключение (ошибка конфигурации).
    """
    status = (
        db.query(models.RequestStatus)
        .filter(models.RequestStatus.name == "Новая заявка")
        .first()
    )
    if status:
        return status

    status = (
        db.query(models.RequestStatus)
        .filter(models.RequestStatus.is_final.is_(False))
        .order_by(models.RequestStatus.id.asc())
        .first()
    )
    if not status:
        raise RuntimeError(
            "В системе не настроен ни один не финальный статус заявки.",
        )

    return status


def build_quality_survey_url(request_id: Optional[int] = None) -> str:
    """
    Формирует URL для перехода к опросу качества работы.

    Можно переопределить базовый URL через переменную окружения QUALITY_SURVEY_URL.
    При передаче request_id добавляет его как параметр запроса.
    """
    base = os.getenv("QUALITY_SURVEY_URL", QUALITY_SURVEY_BASE_URL)

    if request_id is None:
        return base

    separator = "&" if "?" in base else "?"
    return f"{base}{separator}request_id={request_id}"