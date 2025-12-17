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

    equipment_type_id   INTEGER NOT NULL REFERENCES equipment_type(id),
    equipment_model     VARCHAR(200) NOT NULL,

    problem_description TEXT NOT NULL,

    status_id           INTEGER NOT NULL REFERENCES request_status(id),
    completion_date     DATE NULL,

    repair_parts        TEXT NULL,

    master_id           INTEGER NULL REFERENCES app_user(id),
    client_id           INTEGER NOT NULL REFERENCES app_user(id),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_repair_request_status ON repair_request(status_id);
CREATE INDEX IF NOT EXISTS ix_repair_request_equipment_type ON repair_request(equipment_type_id);
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

COMMIT;