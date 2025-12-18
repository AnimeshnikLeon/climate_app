-- Набор запросов для отчетов (Задание 2)

-- Отчет 1: Список заявок с деталями (для печати/выгрузки)
SELECT
    rr.id AS request_id,
    rr.start_date,
    et.name AS equipment_type,
    em.name AS equipment_model,
    it.name AS issue_type,
    rr.problem_description,
    rs.name AS status,
    rr.completion_date,
    rr.repair_parts,
    master_user.fio AS master_fio,
    client_user.fio AS client_fio,
    client_user.phone AS client_phone
FROM repair_request rr
JOIN equipment_model em ON em.id = rr.equipment_model_id
JOIN equipment_type et ON et.id = em.equipment_type_id
JOIN issue_type it ON it.id = rr.issue_type_id
JOIN request_status rs ON rs.id = rr.status_id
JOIN app_user client_user ON client_user.id = rr.client_id
LEFT JOIN app_user master_user ON master_user.id = rr.master_id
ORDER BY rr.id DESC;

-- Отчет 2: Количество выполненных заявок по типам оборудования
SELECT
    et.name AS equipment_type,
    COUNT(*) AS completed_count
FROM repair_request rr
JOIN equipment_model em ON em.id = rr.equipment_model_id
JOIN equipment_type et ON et.id = em.equipment_type_id
JOIN request_status rs ON rs.id = rr.status_id
WHERE rs.is_final = TRUE
GROUP BY et.name
ORDER BY completed_count DESC, et.name;

-- Отчет 3: Среднее время ремонта (в днях) по типам оборудования
SELECT
    et.name AS equipment_type,
    ROUND(AVG((rr.completion_date - rr.start_date)::numeric), 2) AS avg_days
FROM repair_request rr
JOIN equipment_model em ON em.id = rr.equipment_model_id
JOIN equipment_type et ON et.id = em.equipment_type_id
JOIN request_status rs ON rs.id = rr.status_id
WHERE rs.is_final = TRUE
  AND rr.completion_date IS NOT NULL
  AND rr.completion_date >= rr.start_date
GROUP BY et.name
ORDER BY avg_days DESC NULLS LAST, et.name;

-- Отчет 4: Топ типов неисправностей
SELECT
    it.name AS issue_type,
    COUNT(*) AS cnt
FROM repair_request rr
JOIN issue_type it ON it.id = rr.issue_type_id
GROUP BY it.name
ORDER BY cnt DESC, it.name;

-- Отчет 5: Нагрузка специалистов (активные заявки, не финальные)
SELECT
    u.id AS master_id,
    u.fio AS master_fio,
    COUNT(*) AS active_requests
FROM repair_request rr
JOIN request_status rs ON rs.id = rr.status_id
JOIN app_user u ON u.id = rr.master_id
WHERE rs.is_final = FALSE
GROUP BY u.id, u.fio
ORDER BY active_requests DESC, u.fio;