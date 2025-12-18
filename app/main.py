from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from fastapi import Depends
from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import models
from . import services
from .database import session_local


app = FastAPI(title="Учет заявок на ремонт климатического оборудования")

base_dir = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(base_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")

app.add_middleware(
    SessionMiddleware,
    secret_key=services.ensure_default_secret_key(),
    max_age=60 * 60 * 8,
    same_site="lax",
)


def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def build_status_messages(request: Request) -> List[Dict[str, Any]]:
    code = request.query_params.get("status")
    if not code:
        return []

    mapping = {
        "login_required": ("warning", "Требуется вход", "Для продолжения войдите в систему."),
        "login_failed": ("error", "Ошибка входа", "Неверный логин или пароль."),
        "logout_ok": ("info", "Выход выполнен", "Сеанс завершён."),
        "request_created": ("success", "Заявка создана", "Новая заявка успешно сохранена."),
        "request_updated": ("success", "Заявка обновлена", "Изменения сохранены."),
        "request_deleted": ("info", "Заявка удалена", "Запись удалена без ошибок."),
        "request_not_found": ("error", "Заявка не найдена", "Запрошенная заявка не существует или уже удалена."),
        "forbidden": ("error", "Доступ запрещён", "У вас нет прав на выполнение этого действия."),
        "comment_added": ("success", "Комментарий добавлен", "Сообщение специалиста сохранено."),
        "no_results": ("info", "Нет результатов", "По заданным условиям заявок не найдено."),
    }

    msg = mapping.get(code)
    if not msg:
        return []

    msg_type, title, text = msg
    return [{"type": msg_type, "title": title, "text": text}]


def parse_int(value: str) -> Optional[int]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def parse_date(value: str, field_errors: Dict[str, str], field_key: str, field_title: str) -> Optional[date]:
    cleaned = (value or "").strip()
    if not cleaned:
        field_errors[field_key] = f"Укажите дату для поля «{field_title}»."
        return None
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError:
        field_errors[field_key] = f"Неверный формат даты для поля «{field_title}». Используйте ГГГГ-ММ-ДД."
        return None


def current_user_optional(request: Request, db: Session) -> Optional[models.User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(models.User, int(user_id))


def role_name(user: Optional[models.User]) -> str:
    if not user:
        return ""
    if not user.role:
        return ""
    return user.role.name


def user_can_view_request(user: models.User, req: models.RepairRequest) -> bool:
    role = role_name(user)
    if role in (services.ROLE_MANAGER, services.ROLE_OPERATOR):
        return True
    if role == services.ROLE_SPECIALIST:
        return req.master_id == user.id
    if role == services.ROLE_CLIENT:
        return req.client_id == user.id
    return False


def user_can_edit_request(user: models.User, req: models.RepairRequest) -> bool:
    role = role_name(user)
    if role in (services.ROLE_MANAGER, services.ROLE_OPERATOR):
        return True
    if role == services.ROLE_SPECIALIST:
        return req.master_id == user.id
    if role == services.ROLE_CLIENT:
        return req.client_id == user.id and not req.status.is_final
    return False


def user_can_delete_request(user: models.User) -> bool:
    return role_name(user) in (services.ROLE_MANAGER, services.ROLE_OPERATOR)


def user_can_add_comment(user: models.User, req: models.RepairRequest) -> bool:
    return role_name(user) == services.ROLE_SPECIALIST and req.master_id == user.id


def get_or_create_equipment_model(db: Session, equipment_type_id: int, model_name: str) -> models.EquipmentModel:
    existing = (
        db.query(models.EquipmentModel)
        .filter(models.EquipmentModel.equipment_type_id == equipment_type_id)
        .filter(models.EquipmentModel.name == model_name)
        .first()
    )
    if existing:
        return existing

    created = models.EquipmentModel(equipment_type_id=equipment_type_id, name=model_name)
    db.add(created)
    db.flush()
    return created


def get_or_create_issue_type(db: Session, problem_description: str) -> models.IssueType:
    name = services.normalize_issue_type_name(problem_description)
    existing = db.query(models.IssueType).filter(models.IssueType.name == name).first()
    if existing:
        return existing

    created = models.IssueType(name=name)
    db.add(created)
    db.flush()
    return created


@app.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/ui/requests", status_code=status.HTTP_302_FOUND)


@app.get("/ui/login", response_class=HTMLResponse)
def ui_login(request: Request):
    context = {
        "request": request,
        "active_page": "login",
        "messages": build_status_messages(request),
        "form_data": {"login": ""},
        "field_errors": {},
        "user": None,
        "role": "",
    }
    return templates.TemplateResponse("login.html", context)


@app.post("/ui/login", response_class=HTMLResponse)
def ui_login_post(
    request: Request,
    login: str = Form(default=""),
    password: str = Form(default=""),
    db: Session = Depends(get_db),
):
    user = services.authenticate_user(db=db, login=login, password=password)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_failed", status_code=status.HTTP_303_SEE_OTHER)

    request.session["user_id"] = user.id
    return RedirectResponse(url="/ui/requests", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/ui/logout")
def ui_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/ui/login?status=logout_ok", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/ui/requests", response_class=HTMLResponse)
def ui_requests_list(
    request: Request,
    q: str = "",
    status_id: str = "",
    equipment_type_id: str = "",
    issue_type_id: str = "",
    db: Session = Depends(get_db),
):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    role = role_name(user)

    query = (
        db.query(models.RepairRequest)
        .join(models.EquipmentModel)
        .join(models.EquipmentType)
        .join(models.IssueType)
        .join(models.RequestStatus)
        .join(models.User, models.RepairRequest.client_id == models.User.id)
        .order_by(models.RepairRequest.id.desc())
    )

    if role == services.ROLE_CLIENT:
        query = query.filter(models.RepairRequest.client_id == user.id)
    if role == services.ROLE_SPECIALIST:
        query = query.filter(models.RepairRequest.master_id == user.id)

    q_clean = (q or "").strip()
    if q_clean:
        if q_clean.isdigit():
            query = query.filter(models.RepairRequest.id == int(q_clean))
        else:
            query = query.filter(models.RepairRequest.problem_description.ilike(f"%{q_clean}%"))

    s_id = parse_int(status_id)
    if s_id:
        query = query.filter(models.RepairRequest.status_id == s_id)

    e_id = parse_int(equipment_type_id)
    if e_id:
        query = query.filter(models.EquipmentModel.equipment_type_id == e_id)

    it_id = parse_int(issue_type_id)
    if it_id:
        query = query.filter(models.RepairRequest.issue_type_id == it_id)

    items = query.all()

    statuses = db.query(models.RequestStatus).order_by(models.RequestStatus.name).all()
    equipment_types = db.query(models.EquipmentType).order_by(models.EquipmentType.name).all()
    issue_types = db.query(models.IssueType).order_by(models.IssueType.name).all()

    messages = build_status_messages(request)
    if not items and (q_clean or s_id or e_id or it_id):
        messages = messages + [{"type": "info", "title": "Нет результатов", "text": "По фильтрам заявки не найдены."}]

    context = {
        "request": request,
        "active_page": "requests",
        "messages": messages,
        "user": user,
        "role": role,
        "requests": items,
        "statuses": statuses,
        "equipment_types": equipment_types,
        "issue_types": issue_types,
        "filters": {"q": q_clean, "status_id": s_id, "equipment_type_id": e_id, "issue_type_id": it_id},
    }
    return templates.TemplateResponse("requests.html", context)


@app.get("/ui/requests/new", response_class=HTMLResponse)
def ui_request_new(request: Request, db: Session = Depends(get_db)):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    role = role_name(user)
    if role not in (services.ROLE_CLIENT, services.ROLE_OPERATOR, services.ROLE_MANAGER):
        return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    statuses = db.query(models.RequestStatus).order_by(models.RequestStatus.name).all()
    equipment_types = db.query(models.EquipmentType).order_by(models.EquipmentType.name).all()
    issue_types = db.query(models.IssueType).order_by(models.IssueType.name).all()

    specialists = (
        db.query(models.User)
        .join(models.UserRole)
        .filter(models.UserRole.name == services.ROLE_SPECIALIST)
        .order_by(models.User.fio)
        .all()
    )

    clients = (
        db.query(models.User)
        .join(models.UserRole)
        .filter(models.UserRole.name == services.ROLE_CLIENT)
        .order_by(models.User.fio)
        .all()
    )

    form_data = {
        "id": "",
        "start_date": date.today().isoformat(),
        "equipment_type_id": "",
        "equipment_model_name": "",
        "issue_type_id": "",
        "problem_description": "",
        "status_id": "",
        "completion_date": "",
        "repair_parts": "",
        "master_id": "",
        "client_id": str(user.id) if role == services.ROLE_CLIENT else "",
    }

    context = {
        "request": request,
        "active_page": "requests",
        "messages": [],
        "user": user,
        "role": role,
        "is_edit": False,
        "form_data": form_data,
        "field_errors": {},
        "statuses": statuses,
        "equipment_types": equipment_types,
        "issue_types": issue_types,
        "specialists": specialists,
        "clients": clients,
    }
    return templates.TemplateResponse("request_form.html", context)


@app.get("/ui/requests/{request_id}", response_class=HTMLResponse)
def ui_request_view(request_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    req = db.get(models.RepairRequest, request_id)
    if not req:
        return RedirectResponse(url="/ui/requests?status=request_not_found", status_code=status.HTTP_303_SEE_OTHER)

    if not user_can_view_request(user=user, req=req):
        return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    comments = (
        db.query(models.RequestComment)
        .filter(models.RequestComment.request_id == request_id)
        .order_by(models.RequestComment.created_at.asc())
        .all()
    )

    context = {
        "request": request,
        "active_page": "requests",
        "messages": build_status_messages(request),
        "user": user,
        "role": role_name(user),
        "req": req,
        "comments": comments,
        "can_edit": user_can_edit_request(user=user, req=req),
        "can_add_comment": user_can_add_comment(user=user, req=req),
        "can_delete": user_can_delete_request(user=user),
    }
    return templates.TemplateResponse("request_view.html", context)


@app.get("/ui/requests/{request_id}/edit", response_class=HTMLResponse)
def ui_request_edit(request_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    req = db.get(models.RepairRequest, request_id)
    if not req:
        return RedirectResponse(url="/ui/requests?status=request_not_found", status_code=status.HTTP_303_SEE_OTHER)

    if not user_can_edit_request(user=user, req=req):
        return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    statuses = db.query(models.RequestStatus).order_by(models.RequestStatus.name).all()
    equipment_types = db.query(models.EquipmentType).order_by(models.EquipmentType.name).all()
    issue_types = db.query(models.IssueType).order_by(models.IssueType.name).all()

    specialists = (
        db.query(models.User)
        .join(models.UserRole)
        .filter(models.UserRole.name == services.ROLE_SPECIALIST)
        .order_by(models.User.fio)
        .all()
    )

    clients = (
        db.query(models.User)
        .join(models.UserRole)
        .filter(models.UserRole.name == services.ROLE_CLIENT)
        .order_by(models.User.fio)
        .all()
    )

    form_data = {
        "id": str(req.id),
        "start_date": req.start_date.isoformat(),
        "equipment_type_id": str(req.equipment_model.equipment_type_id),
        "equipment_model_name": req.equipment_model.name,
        "issue_type_id": str(req.issue_type_id),
        "problem_description": req.problem_description,
        "status_id": str(req.status_id),
        "completion_date": req.completion_date.isoformat() if req.completion_date else "",
        "repair_parts": req.repair_parts or "",
        "master_id": str(req.master_id) if req.master_id else "",
        "client_id": str(req.client_id),
    }

    context = {
        "request": request,
        "active_page": "requests",
        "messages": [],
        "user": user,
        "role": role_name(user),
        "is_edit": True,
        "form_data": form_data,
        "field_errors": {},
        "statuses": statuses,
        "equipment_types": equipment_types,
        "issue_types": issue_types,
        "specialists": specialists,
        "clients": clients,
    }
    return templates.TemplateResponse("request_form.html", context)


@app.post("/ui/requests/save", response_class=HTMLResponse)
def ui_request_save(
    request: Request,
    id: str = Form(default=""),
    start_date_raw: str = Form(default="", alias="start_date"),
    equipment_type_id: str = Form(default=""),
    equipment_model_name: str = Form(default=""),
    issue_type_id: str = Form(default=""),
    problem_description: str = Form(default=""),
    status_id: str = Form(default=""),
    completion_date_raw: str = Form(default="", alias="completion_date"),
    repair_parts: str = Form(default=""),
    master_id: str = Form(default=""),
    client_id: str = Form(default=""),
    db: Session = Depends(get_db),
):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    role = role_name(user)
    is_edit = bool((id or "").strip())
    field_errors: Dict[str, str] = {}

    start_date_val = parse_date(start_date_raw, field_errors, "start_date", "Дата добавления")

    equip_type_id = parse_int(equipment_type_id)
    if not equip_type_id:
        field_errors["equipment_type_id"] = "Выберите тип оборудования."

    model_clean = (equipment_model_name or "").strip()
    if not model_clean:
        field_errors["equipment_model_name"] = "Укажите модель оборудования."

    problem_clean = (problem_description or "").strip()
    if not problem_clean:
        field_errors["problem_description"] = "Опишите проблему."

    st_id = parse_int(status_id)
    if not st_id:
        field_errors["status_id"] = "Выберите статус заявки."

    completion_date_val: Optional[date] = None
    if (completion_date_raw or "").strip():
        completion_date_val = parse_date(completion_date_raw, field_errors, "completion_date", "Дата завершения")

    master_id_val = parse_int(master_id)
    client_id_val = parse_int(client_id)

    if role == services.ROLE_CLIENT:
        client_id_val = user.id

    if not client_id_val:
        field_errors["client_id"] = "Укажите заказчика."

    issue_type_val_id = parse_int(issue_type_id)

    if field_errors:
        statuses = db.query(models.RequestStatus).order_by(models.RequestStatus.name).all()
        equipment_types = db.query(models.EquipmentType).order_by(models.EquipmentType.name).all()
        issue_types = db.query(models.IssueType).order_by(models.IssueType.name).all()

        specialists = (
            db.query(models.User)
            .join(models.UserRole)
            .filter(models.UserRole.name == services.ROLE_SPECIALIST)
            .order_by(models.User.fio)
            .all()
        )

        clients = (
            db.query(models.User)
            .join(models.UserRole)
            .filter(models.UserRole.name == services.ROLE_CLIENT)
            .order_by(models.User.fio)
            .all()
        )

        form_data = {
            "id": (id or "").strip(),
            "start_date": (start_date_raw or "").strip(),
            "equipment_type_id": equip_type_id,
            "equipment_model_name": model_clean,
            "issue_type_id": issue_type_val_id or "",
            "problem_description": problem_clean,
            "status_id": st_id,
            "completion_date": (completion_date_raw or "").strip(),
            "repair_parts": (repair_parts or "").strip(),
            "master_id": master_id_val or "",
            "client_id": client_id_val or "",
        }

        context = {
            "request": request,
            "active_page": "requests",
            "messages": [
                {"type": "error", "title": "Ошибка ввода данных", "text": "Исправьте ошибки в форме и повторите попытку."}
            ],
            "user": user,
            "role": role,
            "is_edit": is_edit,
            "form_data": form_data,
            "field_errors": field_errors,
            "statuses": statuses,
            "equipment_types": equipment_types,
            "issue_types": issue_types,
            "specialists": specialists,
            "clients": clients,
        }
        return templates.TemplateResponse("request_form.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    status_obj = db.get(models.RequestStatus, st_id)
    if not status_obj:
        return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    if is_edit:
        req_id = parse_int(id)
        if not req_id:
            return RedirectResponse(url="/ui/requests?status=request_not_found", status_code=status.HTTP_303_SEE_OTHER)

        req = db.get(models.RepairRequest, req_id)
        if not req:
            return RedirectResponse(url="/ui/requests?status=request_not_found", status_code=status.HTTP_303_SEE_OTHER)

        if not user_can_edit_request(user=user, req=req):
            return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)
    else:
        if role not in (services.ROLE_CLIENT, services.ROLE_OPERATOR, services.ROLE_MANAGER):
            return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)
        req = models.RepairRequest()

    equipment_model = get_or_create_equipment_model(db=db, equipment_type_id=equip_type_id, model_name=model_clean)

    if issue_type_val_id:
        issue_type_obj = db.get(models.IssueType, issue_type_val_id)
        if not issue_type_obj:
            issue_type_obj = get_or_create_issue_type(db=db, problem_description=problem_clean)
    else:
        issue_type_obj = get_or_create_issue_type(db=db, problem_description=problem_clean)

    if status_obj.is_final and completion_date_val is None:
        completion_date_val = date.today()

    req.start_date = start_date_val
    req.equipment_model_id = equipment_model.id
    req.issue_type_id = issue_type_obj.id
    req.problem_description = problem_clean
    req.status_id = st_id
    req.completion_date = completion_date_val
    req.repair_parts = (repair_parts or "").strip() or None
    req.master_id = master_id_val
    req.client_id = int(client_id_val)

    db.add(req)

    try:
        db.commit()
    except Exception:
        db.rollback()
        return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    status_param = "request_updated" if is_edit else "request_created"
    return RedirectResponse(url=f"/ui/requests?status={status_param}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/ui/requests/{request_id}/delete")
def ui_request_delete(request_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    if not user_can_delete_request(user=user):
        return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    req = db.get(models.RepairRequest, request_id)
    if not req:
        return RedirectResponse(url="/ui/requests?status=request_not_found", status_code=status.HTTP_303_SEE_OTHER)

    db.delete(req)
    db.commit()
    return RedirectResponse(url="/ui/requests?status=request_deleted", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/ui/requests/{request_id}/comment")
def ui_add_comment(
    request_id: int,
    request: Request,
    message: str = Form(default=""),
    db: Session = Depends(get_db),
):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    req = db.get(models.RepairRequest, request_id)
    if not req:
        return RedirectResponse(url="/ui/requests?status=request_not_found", status_code=status.HTTP_303_SEE_OTHER)

    if not user_can_add_comment(user=user, req=req):
        return RedirectResponse(url=f"/ui/requests/{request_id}?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    msg_clean = (message or "").strip()
    if not msg_clean:
        return RedirectResponse(url=f"/ui/requests/{request_id}?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    comment = models.RequestComment(request_id=request_id, master_id=user.id, message=msg_clean)
    db.add(comment)
    db.commit()

    return RedirectResponse(url=f"/ui/requests/{request_id}?status=comment_added", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/ui/users", response_class=HTMLResponse)
def ui_users_list(request: Request, db: Session = Depends(get_db)):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    if role_name(user) != services.ROLE_MANAGER:
        return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    users = db.query(models.User).join(models.UserRole).order_by(models.User.fio).all()

    context = {
        "request": request,
        "active_page": "users",
        "messages": build_status_messages(request),
        "user": user,
        "role": role_name(user),
        "users": users,
    }
    return templates.TemplateResponse("users.html", context)


@app.get("/ui/statistics", response_class=HTMLResponse)
def ui_statistics(request: Request, db: Session = Depends(get_db)):
    user = current_user_optional(request=request, db=db)
    if not user:
        return RedirectResponse(url="/ui/login?status=login_required", status_code=status.HTTP_303_SEE_OTHER)

    if role_name(user) != services.ROLE_MANAGER:
        return RedirectResponse(url="/ui/requests?status=forbidden", status_code=status.HTTP_303_SEE_OTHER)

    stats = services.calculate_statistics(db=db)

    context = {
        "request": request,
        "active_page": "statistics",
        "messages": build_status_messages(request),
        "user": user,
        "role": role_name(user),
        "stats": stats,
    }
    return templates.TemplateResponse("statistics.html", context)


@app.get("/health")
def health():
    return {"ok": True}