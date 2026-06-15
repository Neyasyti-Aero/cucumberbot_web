# CucumberBot Web

Веб-платформа управления мобильным роботом-огурцоводом на базе ROS:
дашборд телеметрии, редактор карт, терминал и админ-панель.

Подробная архитектура и схема взаимодействия компонентов — в [ARCHITECTURE.md](ARCHITECTURE.md).

## Стек

- **Backend**: FastAPI (Clean Architecture: domain → use_cases → interface_adapters → frameworks), SQLAlchemy (async) + Alembic, PostgreSQL
- **Frontend**: React + TypeScript (Feature-Sliced Design), Mantine UI, Zustand, TanStack Query, i18n
- **Хранилище**: PostgreSQL (метаданные), MinIO S3 (карты, логи, снапшоты)
- **Робот**: rosbridge_server (WebSocket :9090), FastAPI держит persistent-подключение
- **Инфраструктура**: Docker Compose, Nginx (фронтенд + проксирование `/api`)

## Структура проекта

```
.
├── ARCHITECTURE.md   # архитектурная схема и ROS-интеграция
├── backend/          # FastAPI приложение
│   ├── src/
│   │   ├── domain/
│   │   ├── use_cases/
│   │   ├── interface_adapters/
│   │   └── frameworks/
│   ├── alembic/       # миграции БД
│   ├── Dockerfile
│   └── .env.example
├── frontend/          # React SPA
│   ├── src/
│   │   ├── app/ pages/ widgets/ features/ entities/ shared/
│   ├── Dockerfile
│   └── nginx.conf
└── docker/
    ├── docker-compose.yml
    └── .env.example
```

## Развёртывание через Docker Compose (основной способ)

Требуется Docker и Docker Compose.

1. Скопировать файл с переменными окружения и заполнить значения:

   ```bash
   cd docker
   cp .env.example .env
   ```

2. **Обязательно изменить перед продакшен-деплоем** в `docker/.env`:
   - `JWT_SECRET` — длинная случайная строка (≥ 32 символов)
   - `DB_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD` — учётные данные дефолтного администратора (создаётся миграцией Alembic `001`)
   - `ROSBRIDGE_URL` — адрес `rosbridge_server` на роботе, например `ws://<robot-ip>:9090`
   - `DEBUG=false`

3. Запуск:

   ```bash
   docker compose up -d --build
   ```

   - Frontend (Nginx): `http://localhost`
   - Backend API: `http://localhost:8000`
   - MinIO консоль: `http://localhost:9001`

   При старте backend-контейнера автоматически применяются миграции (`alembic upgrade head`).

4. Сервис `rosbridge` включён в профиль `demo` (тестовый ROS-узел в контейнере, не для прода):

   ```bash
   docker compose --profile demo up -d
   ```

   В реальном развёртывании робот поднимает `rosbridge_server` самостоятельно — нужно только указать его адрес в `ROSBRIDGE_URL`.

### Переменные окружения (`docker/.env`)

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `DB_PASSWORD` | пароль PostgreSQL | `postgres` |
| `JWT_SECRET` | секрет для подписи JWT (access/refresh) | — |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | доступ к MinIO S3 | `minioadmin` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | учётка admin, создаётся миграцией | `admin@cucumberbot.io` / `Admin1234!` |
| `ROSBRIDGE_URL` | адрес rosbridge_server робота | `ws://rosbridge:9090` |
| `DEBUG` | включает `/api/docs`, `/api/redoc` | `false` |

## Локальная разработка

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows; на Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env     # Linux/macOS: cp .env.example .env
alembic upgrade head
uvicorn main:app --reload
```

API: `http://localhost:8000`, Swagger UI (при `DEBUG=true`): `http://localhost:8000/api/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev-сервер Vite (`http://localhost:5173`) проксирует `/api` и `/ws` на `http://localhost:8000` (см. `vite.config.ts`) — backend должен быть запущен отдельно (локально или через `docker compose up db minio backend`).

## Основные API-эндпоинты

- `POST /api/v1/auth/login`, `/refresh` — аутентификация (JWT access/refresh)
- `POST /api/v1/robot/command` — команды роботу (`patrol`, `collect`, `return_to_base`, `stop`)
- `GET /api/v1/robot/ws/telemetry` — WebSocket-стрим телеметрии (`/odom`, `/battery_state`, `/task_status`)
- `/api/v1/maps/` — загрузка и хранение карт (`.pgm`/`.yaml`/GeoJSON) в MinIO
- `/api/v1/qr/` — генерация QR-кодов с привязкой к координатам карты
- `/api/v1/terminal/ws` — безопасный терминал (whitelist команд, без `shell=True`)
- `/api/v1/users/` — управление пользователями (роли `admin`/`operator`)

## Чек-лист перед продакшен-деплоем

- [ ] Сменить `JWT_SECRET`, пароли БД/MinIO и пароль дефолтного администратора
- [ ] `DEBUG=false` (отключает Swagger/Redoc)
- [ ] Сузить `allow_origins` в CORS-настройках backend (`backend/main.py`) до реального домена фронтенда
- [ ] Настроить TLS (например, через Nginx/reverse proxy перед сервисами `frontend`/`backend`)
- [ ] Указать корректный `ROSBRIDGE_URL` робота, профиль `demo` не использовать в проде
- [ ] Сменить пароль администратора после первого входа
