-- Набор запросов и представлений для отчетов (Задание 2)
-- Файл можно запускать многократно: используются CREATE OR REPLACE VIEW.

-- =========================================================
-- Отчет 1: Список заявок с деталями (для печати/выгрузки)
-- =========================================================

CREATE OR REPLACE VIEW v_request_full AS
SELECT
    rr.id                    AS request_id,
    rr.start_date            AS start_date,
    et.name                  AS equipment_type,
    em.name                  AS equipment_model,
    it.name                  AS issue_type,
    rr.problem_description   AS problem_description,
    rs.name                  AS status,
    rs.is_final              AS status_is_final,
    rr.completion_date       AS completion_date,
    rr.repair_parts          AS repair_parts,
    master_user.id           AS master_id,
    master_user.fio          AS master_fio,
    client_user.id           AS client_id,
    client_user.fio          AS client_fio,
    client_user.phone        AS client_phone,
    rr.created_at            AS created_at,
    rr.updated_at            AS updated_at
FROM repair_request rr
JOIN equipment_model em
    ON em.id = rr.equipment_model_id
JOIN equipment_type et
    ON et.id = em.equipment_type_id
JOIN issue_type it
    ON it.id = rr.issue_type_id
JOIN request_status rs
    ON rs.id = rr.status_id
JOIN app_user client_user
    ON client_user.id = rr.client_id
LEFT JOIN app_user master_user
    ON master_user.id = rr.master_id;

-- Пример использования:
-- SELECT * FROM v_request_full ORDER BY request_id DESC;


-- =========================================================
-- Отчет 2: Количество выполненных заявок по типам оборудования
-- =========================================================

CREATE OR REPLACE VIEW v_equipment_completed_stats AS
SELECT
    et.name      AS equipment_type,
    COUNT(*)     AS completed_count
FROM repair_request rr
JOIN equipment_model em
    ON em.id = rr.equipment_model_id
JOIN equipment_type et
    ON et.id = em.equipment_type_id
JOIN request_status rs
    ON rs.id = rr.status_id
WHERE rs.is_final = TRUE
GROUP BY et.name;

-- Пример использования:
-- SELECT * FROM v_equipment_completed_stats
-- ORDER BY completed_count DESC, equipment_type;


-- =========================================================
-- Отчет 3: Среднее время ремонта (в днях) по типам оборудования
-- =========================================================

CREATE OR REPLACE VIEW v_equipment_avg_repair_time AS
SELECT
    et.name AS equipment_type,
    ROUND(
        AVG((rr.completion_date - rr.start_date)::numeric),
        2
    ) AS avg_days
FROM repair_request rr
JOIN equipment_model em
    ON em.id = rr.equipment_model_id
JOIN equipment_type et
    ON et.id = em.equipment_type_id
JOIN request_status rs
    ON rs.id = rr.status_id
WHERE rs.is_final = TRUE
  AND rr.completion_date IS NOT NULL
  AND rr.completion_date >= rr.start_date
GROUP BY et.name;

-- Пример использования:
-- SELECT * FROM v_equipment_avg_repair_time
-- ORDER BY avg_days DESC NULLS LAST, equipment_type;


-- =========================================================
-- Отчет 4: Топ типов неисправностей
-- =========================================================

CREATE OR REPLACE VIEW v_issue_type_stats AS
SELECT
    it.name AS issue_type,
    COUNT(*) AS cnt
FROM repair_request rr
JOIN issue_type it
    ON it.id = rr.issue_type_id
GROUP BY it.name;

-- Пример использования:
-- SELECT * FROM v_issue_type_stats
-- ORDER BY cnt DESC, issue_type;


-- =========================================================
-- Отчет 5: Нагрузка специалистов (активные заявки, не финальные)
-- =========================================================

CREATE OR REPLACE VIEW v_specialist_active_load AS
SELECT
    u.id     AS master_id,
    u.fio    AS master_fio,
    COUNT(*) AS active_requests
FROM repair_request rr
JOIN request_status rs
    ON rs.id = rr.status_id
JOIN app_user u
    ON u.id = rr.master_id
JOIN user_role ur
    ON ur.id = u.role_id
WHERE rs.is_final = FALSE
  AND ur.name = 'Специалист'
GROUP BY u.id, u.fio;

-- Пример использования:
-- SELECT * FROM v_specialist_active_load
-- ORDER BY active_requests DESC, master_fio;