BEGIN;

CREATE TABLE IF NOT EXISTS user_role (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS request_status (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(60) NOT NULL UNIQUE,
    is_final    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS equipment_type (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS equipment_model (
    id                  SERIAL PRIMARY KEY,
    equipment_type_id   INTEGER NOT NULL REFERENCES equipment_type(id),
    name                VARCHAR(200) NOT NULL,
    CONSTRAINT uq_equipment_model_type_name UNIQUE (equipment_type_id, name)
);

CREATE TABLE IF NOT EXISTS issue_type (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS app_user (
    id              SERIAL PRIMARY KEY,
    fio             VARCHAR(255) NOT NULL,
    phone           VARCHAR(20) NOT NULL,
    login           VARCHAR(60) NOT NULL UNIQUE,
    password_hash   VARCHAR(300) NOT NULL,
    role_id         INTEGER NOT NULL REFERENCES user_role(id)
);

CREATE TABLE IF NOT EXISTS repair_request (
    id                  SERIAL PRIMARY KEY,
    start_date          DATE NOT NULL,

    equipment_model_id  INTEGER NOT NULL REFERENCES equipment_model(id),
    issue_type_id       INTEGER NOT NULL REFERENCES issue_type(id),

    problem_description TEXT NOT NULL,

    status_id           INTEGER NOT NULL REFERENCES request_status(id),
    completion_date     DATE NULL,

    repair_parts        TEXT NULL,

    master_id           INTEGER NULL REFERENCES app_user(id),
    client_id           INTEGER NOT NULL REFERENCES app_user(id),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_repair_request_completion_date
        CHECK (completion_date IS NULL OR completion_date >= start_date)
);

CREATE INDEX IF NOT EXISTS ix_repair_request_status ON repair_request(status_id);
CREATE INDEX IF NOT EXISTS ix_repair_request_equipment_model ON repair_request(equipment_model_id);
CREATE INDEX IF NOT EXISTS ix_repair_request_issue_type ON repair_request(issue_type_id);
CREATE INDEX IF NOT EXISTS ix_repair_request_client ON repair_request(client_id);
CREATE INDEX IF NOT EXISTS ix_repair_request_master ON repair_request(master_id);

CREATE TABLE IF NOT EXISTS request_comment (
    id          SERIAL PRIMARY KEY,
    request_id  INTEGER NOT NULL REFERENCES repair_request(id) ON DELETE CASCADE,
    master_id   INTEGER NOT NULL REFERENCES app_user(id),
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_request_comment_request ON request_comment(request_id);

-- ===========================
-- Триггеры валидации ролей
-- ===========================

CREATE OR REPLACE FUNCTION validate_repair_request_roles_and_dates()
RETURNS trigger AS $$
DECLARE
    client_role TEXT;
    master_role TEXT;
    status_final BOOLEAN;
BEGIN
    SELECT ur.name
    INTO client_role
    FROM app_user u
    JOIN user_role ur ON ur.id = u.role_id
    WHERE u.id = NEW.client_id;

    IF client_role IS NULL OR client_role <> 'Заказчик' THEN
        RAISE EXCEPTION 'client_id must reference user with role "Заказчик"';
    END IF;

    IF NEW.master_id IS NOT NULL THEN
        SELECT ur.name
        INTO master_role
        FROM app_user u
        JOIN user_role ur ON ur.id = u.role_id
        WHERE u.id = NEW.master_id;

        IF master_role IS NULL OR master_role <> 'Специалист' THEN
            RAISE EXCEPTION 'master_id must reference user with role "Специалист"';
        END IF;
    END IF;

    SELECT rs.is_final
    INTO status_final
    FROM request_status rs
    WHERE rs.id = NEW.status_id;

    IF status_final IS TRUE AND NEW.completion_date IS NULL THEN
        NEW.completion_date := CURRENT_DATE;
    END IF;

    NEW.updated_at := NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_repair_request ON repair_request;
CREATE TRIGGER trg_validate_repair_request
BEFORE INSERT OR UPDATE ON repair_request
FOR EACH ROW
EXECUTE FUNCTION validate_repair_request_roles_and_dates();

CREATE OR REPLACE FUNCTION validate_request_comment_master_role()
RETURNS trigger AS $$
DECLARE
    master_role TEXT;
BEGIN
    SELECT ur.name
    INTO master_role
    FROM app_user u
    JOIN user_role ur ON ur.id = u.role_id
    WHERE u.id = NEW.master_id;

    IF master_role IS NULL OR master_role <> 'Специалист' THEN
        RAISE EXCEPTION 'request_comment.master_id must reference user with role "Специалист"';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_request_comment ON request_comment;
CREATE TRIGGER trg_validate_request_comment
BEFORE INSERT OR UPDATE ON request_comment
FOR EACH ROW
EXECUTE FUNCTION validate_request_comment_master_role();

COMMIT;