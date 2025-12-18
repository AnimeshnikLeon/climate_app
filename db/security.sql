-- Демонстрационная настройка групп/ролей в СУБД (Задание 2)
-- В реальном проекте приложение обычно подключается одним тех.пользователем,
-- а роли предметной области реализуются на уровне приложения.
-- Этот скрипт показывает, как можно разделить доступ и на уровне PostgreSQL.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_manager') THEN
        CREATE ROLE svc_manager NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_operator') THEN
        CREATE ROLE svc_operator NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_specialist') THEN
        CREATE ROLE svc_specialist NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_client') THEN
        CREATE ROLE svc_client NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO svc_manager, svc_operator, svc_specialist, svc_client;

-- Менеджер: полный доступ
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO svc_manager;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO svc_manager;

-- Оператор: справочники + заявки/комментарии
GRANT SELECT ON user_role, request_status, equipment_type, equipment_model, issue_type TO svc_operator;
GRANT SELECT, INSERT, UPDATE, DELETE ON repair_request, request_comment TO svc_operator;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO svc_operator;

-- Специалист: справочники + чтение заявок/комментариев (детальная ограничительная политика обычно через RLS)
GRANT SELECT ON user_role, request_status, equipment_type, equipment_model, issue_type TO svc_specialist;
GRANT SELECT, INSERT ON request_comment TO svc_specialist;
GRANT SELECT, UPDATE ON repair_request TO svc_specialist;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO svc_specialist;

-- Заказчик: справочники + создание заявок
GRANT SELECT ON request_status, equipment_type, equipment_model, issue_type TO svc_client;
GRANT SELECT, INSERT, UPDATE ON repair_request TO svc_client;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO svc_client;