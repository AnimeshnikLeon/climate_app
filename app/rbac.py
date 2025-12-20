from typing import Optional

from . import models
from . import services


def role_name(user: Optional[models.User]) -> str:
    """
    Безопасно возвращает название роли пользователя.
    При отсутствии пользователя или роли возвращает пустую строку.
    """
    if not user:
        return ""
    if not user.role:
        return ""

    return user.role.name


def user_can_create_request(user: models.User) -> bool:
    """
    Право создания новой заявки:
    - Менеджер, Оператор, Менеджер по качеству, Заказчик.
    Специалист создаёт заявки только по распоряжению оператора/менеджера.
    """
    r = role_name(user)
    return r in (
        services.ROLE_MANAGER,
        services.ROLE_OPERATOR,
        services.ROLE_QUALITY_MANAGER,
        services.ROLE_CLIENT,
    )


def user_can_view_request(user: models.User, req: models.RepairRequest) -> bool:
    """
    Право просмотра заявки:
    - Менеджер, Оператор, Менеджер по качеству: все заявки;
    - Специалист: только свои (master_id = user.id);
    - Заказчик: только свои (client_id = user.id).
    """
    r = role_name(user)

    if r in (
        services.ROLE_MANAGER,
        services.ROLE_OPERATOR,
        services.ROLE_QUALITY_MANAGER,
    ):
        return True

    if r == services.ROLE_SPECIALIST:
        return req.master_id == user.id

    if r == services.ROLE_CLIENT:
        return req.client_id == user.id

    return False


def user_can_edit_request(user: models.User, req: models.RepairRequest) -> bool:
    """
    Право редактирования заявки:
    - Менеджер, Оператор, Менеджер по качеству: любые заявки;
    - Специалист: только свои заявки;
    - Заказчик: только свою заявку и только пока статус не финальный.
    """
    r = role_name(user)

    if r in (
        services.ROLE_MANAGER,
        services.ROLE_OPERATOR,
        services.ROLE_QUALITY_MANAGER,
    ):
        return True

    if r == services.ROLE_SPECIALIST:
        return req.master_id == user.id

    if r == services.ROLE_CLIENT:
        return req.client_id == user.id and not bool(req.status.is_final)

    return False


def user_can_delete_request(user: models.User) -> bool:
    """
    Право удаления заявки:
    - Только Менеджер и Оператор.
    """
    r = role_name(user)
    return r in (services.ROLE_MANAGER, services.ROLE_OPERATOR)


def user_can_add_comment(user: models.User, req: models.RepairRequest) -> bool:
    """
    Право добавления комментария:
    - Только специалист по своей заявке.
    """
    r = role_name(user)
    return r == services.ROLE_SPECIALIST and req.master_id == user.id


def user_can_assign_master(user: models.User) -> bool:
    """
    Право назначения/смены исполнителя (master_id) у заявки:
    - Менеджер, Оператор, Менеджер по качеству.
    """
    r = role_name(user)
    return r in (
        services.ROLE_MANAGER,
        services.ROLE_OPERATOR,
        services.ROLE_QUALITY_MANAGER,
    )


def user_can_change_status(
    user: models.User,
    old_status: models.RequestStatus,
    new_status: models.RequestStatus,
) -> bool:
    """
    Право смены статуса заявки.

    Правила:
    - Менеджер, Оператор, Менеджер по качеству: любые переходы между статусами;
    - Специалист:
        - может переводить свои заявки между любыми статусами,
        - но не может «раскрывать» финальную заявку обратно в не финальный статус;
    - Заказчик:
        - не имеет права менять статус (только читать).
    """
    r = role_name(user)

    if r in (
        services.ROLE_MANAGER,
        services.ROLE_OPERATOR,
        services.ROLE_QUALITY_MANAGER,
    ):
        return True

    if r == services.ROLE_SPECIALIST:
        if old_status.id == new_status.id:
            return True
        if old_status.is_final and not new_status.is_final:
            return False
        return True

    if r == services.ROLE_CLIENT:
        return old_status.id == new_status.id

    return False


def user_can_manage_users(user: models.User) -> bool:
    """
    Право управления пользователями:
    - Справочник пользователей, их роли, пароли и т.п.
    """
    return role_name(user) == services.ROLE_MANAGER


def user_can_view_statistics(user: models.User) -> bool:
    """
    Право просмотра статистики работы отдела:
    - Только Менеджер.
    """
    return role_name(user) == services.ROLE_MANAGER