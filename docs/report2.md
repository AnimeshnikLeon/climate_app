# Задание 2 (Неделя 2). ERD, 3НФ, БД, импорт, отчеты, backup, доступ

## 1) ER-диаграмма и 3НФ

### 1.1. Сущности

- `user_role` — роли пользователей (Менеджер / Оператор / Специалист / Заказчик).
- `app_user` — пользователи системы.
- `request_status` — статусы заявки (с признаком финальности `is_final`).
- `equipment_type` — тип оборудования.
- `equipment_model` — модель оборудования (привязана к типу).
- `issue_type` — тип неисправности (справочник для отчетности и статистики).
- `repair_request` — заявка на ремонт.
- `request_comment` — комментарии специалистов по заявкам.

### 1.2. Нормализация до 3НФ

Сделано:

- Повторяющиеся текстовые значения вынесены в справочники:
  - типы оборудования → `equipment_type`;
  - модели оборудования → `equipment_model` (уникальность по паре `equipment_type_id + name`);
  - типы неисправностей → `issue_type`;
  - статусы заявок → `request_status`;
  - роли пользователей → `user_role`.
- Таблица `repair_request` содержит только:
  - ссылки на справочники (`FK`),
  - атрибуты самой заявки (даты, описание, комплектующие, ссылки на специалиста/клиента).
- Таблица `request_comment` содержит:
  - атрибуты комментария (сообщение, дата),
  - ссылки на заявку и автора-комментатора.

Таким образом:

- нет функциональных зависимостей атрибутов от части составного ключа;
- нет транзитивных зависимостей неключевых атрибутов от первичного ключа — данные находятся в 3НФ.

### 1.3. ERD

ER-диаграмма описана в файле `docs/er_diagram.mmd` в формате Mermaid:

- удобно просматривать прямо в редакторе (VS Code + Mermaid preview) или через онлайн‑рендер;
- для сдачи можно экспортировать диаграмму в PDF из DBeaver/pgAdmin.

Фрагмент связей:

- `USER_ROLE ||--o{ APP_USER : role_id`
- `EQUIPMENT_TYPE ||--o{ EQUIPMENT_MODEL : equipment_type_id`
- `EQUIPMENT_MODEL ||--o{ REPAIR_REQUEST : equipment_model_id`
- `ISSUE_TYPE ||--o{ REPAIR_REQUEST : issue_type_id`
- `REQUEST_STATUS ||--o{ REPAIR_REQUEST : status_id`
- `APP_USER ||--o{ REPAIR_REQUEST : client_id`
- `APP_USER ||--o{ REPAIR_REQUEST : master_id`
- `REPAIR_REQUEST ||--o{ REQUEST_COMMENT : request_id`
- `APP_USER ||--o{ REQUEST_COMMENT : master_id`

## 2) Ссылочная целостность и ограничения

Реализация — файл `db/init.sql`.

### 2.1. Первичные и внешние ключи

- PK во всех таблицах (`id SERIAL PRIMARY KEY`).
- FK:
  - `app_user.role_id -> user_role.id`;
  - `equipment_model.equipment_type_id -> equipment_type.id`;
  - `repair_request.equipment_model_id -> equipment_model.id`;
  - `repair_request.issue_type_id -> issue_type.id`;
  - `repair_request.status_id -> request_status.id`;
  - `repair_request.master_id -> app_user.id`;
  - `repair_request.client_id -> app_user.id`;
  - `request_comment.request_id -> repair_request.id (ON DELETE CASCADE)`;
  - `request_comment.master_id -> app_user.id`.

Таким образом, нельзя создать «висящую» запись без связанного справочника.

### 2.2. Уникальности и проверки данных

- Уникальные поля:
  - `user_role.name`;
  - `request_status.name`;
  - `equipment_type.name`;
  - `issue_type.name`;
  - `app_user.login`;
  - `equipment_model(equipment_type_id, name)`.

- Проверка корректности дат заявки:
  - `CHECK (completion_date IS NULL OR completion_date >= start_date)`.

Это защищает от ввода некорректных дат окончания ремонта.

### 2.3. Триггеры бизнес‑логики на уровне БД

В `init.sql` реализованы функции и триггеры:

1. `validate_repair_request_roles_and_dates` (до/после INSERT/UPDATE `repair_request`):
   - проверяет, что:
     - `client_id` ссылается на пользователя с ролью «Заказчик»;
     - `master_id` (если задан) ссылается на пользователя с ролью «Специалист».
   - если статус заявки финальный (`request_status.is_final = TRUE`), а `completion_date` не указана —
     автоматически проставляет текущую дату;
   - обновляет поле `updated_at` при каждом изменении записи.

2. `validate_request_comment_master_role` (до INSERT/UPDATE `request_comment`):
   - гарантирует, что `master_id` принадлежит пользователю с ролью «Специалист».

Таким образом, базовые правила предметной области соблюдаются даже при обходе приложения (через чистый SQL).

### 2.4. Индексы

Созданы индексы для наиболее часто используемых полей:

- `ix_repair_request_status` — поиск по статусу;
- `ix_repair_request_equipment_model` — фильтрация по типу/модели оборудования;
- `ix_repair_request_issue_type` — фильтрация по типу неисправности;
- `ix_repair_request_client` — выборка заявок по клиенту;
- `ix_repair_request_master` — выборка заявок по специалисту;
- `ix_request_comment_request` — выборка комментариев по заявке.

Они используются как в веб‑интерфейсе (страница заявок и статистика), так и в SQL‑отчетах.

## 3) Создание БД и таблиц

### 3.1. Автоматический запуск в Docker

При первом старте контейнера PostgreSQL:

- выполняется скрипт `db/init.sql` через механизм `docker-entrypoint-initdb.d`;
- создаются все таблицы, ограничения, индексы и триггеры.

Команда запуска:

```bash
cp .env.example .env
docker compose up --build
```

После этого база готова к импорту данных и работе приложения.

## 4) Импорт данных заказчика

### 4.1. Исходные файлы

Каталог `data/import/`:

- `inputDataUsers.csv` — пользователи (ФИО, телефон, логин, пароль, тип/роль);
- `inputDataRequests.csv` — заявки;
- `inputDataComments.csv` — комментарии.

Формат CSV — `;` (точка с запятой).

### 4.2. Скрипт импорта

Используется контейнер `importer` и скрипт `scripts/import_data.py`:

- создает необходимые записи в справочниках:
  - роли,
  - статусы,
  - типы оборудования,
  - модели оборудования,
  - типы неисправностей (через `normalize_issue_type_name`);
- импортирует пользователей:
  - пароли хэшируются через `PBKDF2-HMAC-SHA256` (`services.hash_password`);
  - роли подтягиваются из `user_role` по названию;
- импортирует заявки:
  - по текстовому названию типа и модели ищутся `equipment_type` и `equipment_model`;
  - тип неисправности определяется через справочник `issue_type`;
  - статусы подтягиваются по имени;
  - ссылки на клиентов и исполнителей подставляются по `id`;
- импортирует комментарии:
  - привязка к заявкам и мастерам по идентификаторам.

Импорт идемпотентен: используются `INSERT ... ON CONFLICT DO UPDATE`, что позволяет повторно заливать данные без дублирования.

Запуск импорта в Docker:

```bash
docker compose up --build
# после успешного старта db/app автоматически стартует контейнер importer
# и выполняет загрузку CSV
```

## 5) Запросы и отчеты

### 5.1. Представления (VIEW) для отчетов

В файле `db/reports.sql` реализованы представления для основных отчетов:

1. `v_request_full` — полная карточка заявки:
   - идентификатор, даты создания/завершения;
   - тип/модель оборудования;
   - тип неисправности и описание проблемы;
   - статус и признак финальности;
   - комплектующие;
   - ФИО и телефон клиента;
   - ФИО исполнителя (если назначен).

   Пример использования:

   ```sql
   SELECT * FROM v_request_full
   ORDER BY request_id DESC;
   ```

2. `v_equipment_completed_stats` — количество выполненных заявок по типам оборудования:

   ```sql
   SELECT * FROM v_equipment_completed_stats
   ORDER BY completed_count DESC, equipment_type;
   ```

3. `v_equipment_avg_repair_time` — среднее время ремонта (в днях) по типам оборудования
   (учитываются только финальные заявки с корректной датой завершения):

   ```sql
   SELECT * FROM v_equipment_avg_repair_time
   ORDER BY avg_days DESC NULLS LAST, equipment_type;
   ```

4. `v_issue_type_stats` — статистика по типам неисправностей:

   ```sql
   SELECT * FROM v_issue_type_stats
   ORDER BY cnt DESC, issue_type;
   ```

5. `v_specialist_active_load` — нагрузка специалистов (количество активных, не финальных заявок):

   ```sql
   SELECT * FROM v_specialist_active_load
   ORDER BY active_requests DESC, master_fio;
   ```

Эти представления можно использовать:

- в интерфейсе приложения (например, для выгрузки в Excel/CSV);
- в сторонних системах отчетности (BI, отчеты преподавателя);
- в SQL‑клиенте (DBeaver, pgAdmin) как готовые «представления для печати».

Если в учебной среде запрещено создание VIEW, в `reports.sql` также сохранены исходные «сырые» SELECT‑запросы в комментариях.

### 5.2. Взаимосвязь с сервисом статистики приложения

Модуль `app/services.py` реализует функцию `calculate_statistics(db)`, которая:

- обходит таблицу `repair_request` и связанные справочники;
- рассчитывает:
  - общее количество заявок;
  - количество выполненных заявок;
  - среднее время ремонта;
  - распределение по типам оборудования;
  - распределение по типам неисправностей;
  - нагрузку специалистов (функция `calculate_specialist_load`, согласована с `v_specialist_active_load`).

Результат отображается на странице `/ui/statistics` (только для роли Менеджер).

## 6) Резервное копирование БД

Скрипты резервного копирования:

- Linux/macOS — `scripts/backup_db.sh`:

  ```bash
  ./scripts/backup_db.sh
  ```

- Windows PowerShell — `scripts/backup_db.ps1`:

  ```powershell
  ./scripts/backup_db.ps1
  ```

Оба скрипта:

- создают директорию `backups/` (если её нет);
- выполняют `pg_dump -F c` из контейнера `climate_db`;
- формируют файлы вида `climate_service_YYYYMMDD_HHMMSS.dump`.

Восстановление (пример):

```bash
# пример восстановления в отдельную БД
createdb climate_service_restore
pg_restore -d climate_service_restore -F c path/to/backup.dump
```

## 7) Принцип регистрации пользователей

Выбран принцип **централизованной регистрации**:

- учетные записи создаются ответственным сотрудником (менеджером/администратором);
- саморегистрация пользователей отключена;
- роли назначаются при создании пользователя (Менеджер/Оператор/Специалист/Заказчик).

Обоснование:

- роли определяют доступ к критичным данным (заявки, статистика, назначение исполнителей);
- самовольная смена роли/регистрации противоречит политике безопасности;
- количество пользователей в учебной предметной области невелико, поэтому нагрузка на администратора допустима.

## 8) Группы пользователей и уровни доступа

Реализованы два уровня управления доступом.

### 8.1. Уровень приложения (RBAC)

На уровне бизнес‑логики приложения используются роли (`user_role.name`):

- Менеджер;
- Оператор;
- Специалист;
- Заказчик.

Проверки сосредоточены в модуле `app/rbac.py`, а также используются в `app/usecases.py`. Основные функции:

- `role_name(user)` — безопасное получение имени роли.
- `user_can_create_request(user)` — право создания заявок.
- `user_can_view_request(user, req)` — право просмотра заявки.
- `user_can_edit_request(user, req)` — право редактирования заявки.
- `user_can_delete_request(user)` — право удаления заявки.
- `user_can_add_comment(user, req)` — право добавления комментария.
- `user_can_assign_master(user)` — право назначения/смены исполнителя.
- `user_can_change_status(user, old_status, new_status)` — право смены статуса (в т.ч. запрет специалисту «раскрывать» финальные заявки).
- `user_can_manage_users(user)` — право управления справочником пользователей.
- `user_can_view_statistics(user)` — право просмотра статистики.

Сценарии работы с заявками реализованы через модуль `app/usecases.py`:

- `save_request(db, user, data)` — создание/обновление заявки по типизированному `RequestInput`;
- `delete_request(db, user, request_id)` — удаление заявки;
- `add_comment(db, user, request_id, message)` — добавление комментария.

Хендлеры FastAPI (`app/main.py`) выполняют:

- разбор и валидацию входных данных (формы);
- вызов соответствующих use case‑функций;
- отображение результатов/ошибок пользователю через статус‑коды (`?status=...`).

### 8.2. Уровень СУБД (демонстрационный)

Для демонстрации разграничения прав в PostgreSQL используется `db/security.sql`:

- создаются роли БД:
  - `svc_manager`;
  - `svc_operator`;
  - `svc_specialist`;
  - `svc_client`;
- на каждую роль назначаются права:
  - Менеджер (`svc_manager`) — полный доступ (SELECT/INSERT/UPDATE/DELETE);
  - Оператор (`svc_operator`) — работа со справочниками и таблицами заявок/комментариев;
  - Специалист (`svc_specialist`) — чтение справочников и заявок, добавление комментариев, обновление своих заявок;
  - Клиент (`svc_client`) — чтение справочников и создание/обновление заявок.