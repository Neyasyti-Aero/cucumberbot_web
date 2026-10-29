# CucumberBot Web

Веб-платформа управления мобильным роботом-огурцоводом на базе ROS:
дашборд телеметрии, редактор карт, терминал и админ-панель.

Подробная архитектура и схема взаимодействия компонентов — в [ARCHITECTURE.md](ARCHITECTURE.md).

**Прод:** https://ogurec.neyasyti.ru — деплой через GitLab CI, инструкция: [deploy/README.md](deploy/README.md).

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
├── docker/
│   ├── docker-compose.yml         # базовый стек (локальная разработка)
│   ├── docker-compose.server.yml  # прод: за Caddy, без открытых портов
│   ├── docker-compose.ci.yml      # системные тесты в CI
│   ├── ros2/                      # ROS 2 Humble: rosbridge + nav2_map_server (тесты, demo)
│   └── .env.example
├── deploy/                # инструкция по деплою, блок Caddy
└── .gitlab-ci.yml         # check → build → system → deploy → verify
```

## Локальный запуск через Docker Compose

Боевой сервер настраивается по [deploy/README.md](deploy/README.md), руками там ничего не запускается.

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

4. Сервис `rosbridge` включён в профиль `demo` (ROS 2 Humble с rosbridge и nav2_map_server, не для прода):

   ```bash
   docker compose --profile demo up -d
   ```

   В реальном развёртывании робот поднимает `rosbridge_server` самостоятельно — нужно только указать его адрес в `ROSBRIDGE_URL`.

Все переменные с комментариями описаны в [`docker/.env.example`](docker/.env.example).

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

Тесты:

```bash
pip install -r requirements-dev.txt
ruff check . && pytest                      # линт + юнит-тесты
# системные — против поднятого стека (см. .gitlab-ci.yml, job system:tests)
SYSTEM_BASE_URL=http://localhost pytest tests/system
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
- `GET /api/v1/health` — статус API и соединения с роботом (`robot_connected`)
- `POST /api/v1/robot/command` — команды роботу (`patrol`, `collect`, `return_to_base`, `stop`)
- `GET /api/v1/robot/pose` — **где робот сейчас**: `x, y, theta` в кадре `map` (AMCL, `/amcl_pose`);
  если локализации нет — одометрия (`frame_id: "odom"`). Поля `stale`/`age_seconds` — свежесть данных
- `GET /api/v1/robot/ws/telemetry` — WebSocket-стрим телеметрии (`/odom`, `/battery_state`, `/task_status`) + `pose`
- `/api/v1/maps/` — карты: загрузка `.pgm` + `map.yaml`, шаблоны из редактора (GeoJSON)
  - `GET /maps/{id}/nav2/validate` — проверка пригодности для Nav2 (размер, origin, свободные/занятые ячейки, предупреждения)
  - `GET /maps/{id}/nav2.zip` — `map.pgm` + `map.yaml` для `nav2_map_server`
  - `POST /maps/{id}/publish` — опубликовать в `/map` (`nav_msgs/msg/OccupancyGrid`, transient local)
- `/api/v1/qr/` — QR-метки с позой в кадре `map`
  - `POST /qr/maps/{id}/sync` — создать метки для QR-точек из редактора (id существующих сохраняются)
  - `GET /qr/maps/{id}/sheet.pdf?size_mm=50` — лист A4 для печати
  - `GET /qr/{qr_id}/image.png?size_mm=&dpi=` — одна метка
  - `GET /qr/maps/{id}/landmarks.yaml` — список меток для узла локализации на роботе
- `/api/v1/terminal/ws` — безопасный терминал (whitelist команд, без `shell=True`)
- `/api/v1/users/` — управление пользователями (роли `admin`/`operator`)

### Карта для Nav2

Карта из редактора растеризуется в occupancy grid: помещение — свободная зона со стенами, снаружи
занято, грядки — препятствия; дорожки, точки, база и QR на проходимость не влияют. Угол помещения
соответствует `(0, 0)` кадра `map` (x вправо, y вверх, REP-103). Пороги `occupied_thresh: 0.65`,
`free_thresh: 0.196`: при nav2-дефолте 0.25 пиксели «неизвестно» (205) становятся свободными.
В CI карта проверяется настоящим `nav2_map_server` и rosbridge на ROS 2 Humble.

## Чек-лист перед продакшен-деплоем

- [ ] Сменить `JWT_SECRET`, пароли БД/MinIO и пароль дефолтного администратора
- [ ] `DEBUG=false` (отключает Swagger/Redoc)
- [ ] `CORS_ORIGINS=https://ogurec.neyasyti.ru`
- [ ] TLS — Caddy на сервере (`deploy/caddy/cucumberbot.conf`)
- [ ] Указать корректный `ROSBRIDGE_URL` робота, профиль `demo` не использовать в проде
- [ ] Сменить пароль администратора после первого входа
