# Учет заявок на ремонт климатического оборудования (Учебная практика)

## Запуск
```bash
cp .env.example .env
docker compose up --build
```

## Вход
Тестовые логины/пароли в `data/import/inputDataUsers.csv`, например:
- Менеджер: `login1 / pass1`
- Специалист: `login2 / pass2`
- Оператор: `login4 / pass4`
- Заказчик: `login7 / pass7`

## Основные страницы
- `/ui/login` — вход
- `/ui/requests` — заявки
- `/ui/requests/new` — новая заявка
- `/ui/requests/{id}` — карточка заявки
- `/ui/statistics` — статистика (Менеджер)
- `/ui/users` — пользователи (Менеджер)

## Документы
- `docs/report1.md` — задание 1
- `docs/report2.md` — задание 2 (ERD/3НФ, импорт, отчеты, резервное копирование, доступ)
- `docs/er_diagram.mmd` — ER-диаграмма в Mermaid формате
- `db/reports.sql` — SQL отчеты
- `db/security.sql` — демонстрация DB-ролей
- `docs/test_protocol.md` — протокол тестирования