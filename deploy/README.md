# Деплой CucumberBot Web

Панель управления роботом живёт на том же сервере, что и сайт `neyasiti-web`, и
деплоится по той же схеме: GitLab-runner (shell) на сервере собирает образы локальным docker'ом и
поднимает стек, Caddy отдаёт его по HTTPS.

**Адрес:** https://cutecumber.neyasyti.ru

```
git.neyasyti.ru                              сервер 4V100 (77.50.187.110 → 192.168.1.2)
┌──────────────┐  runner сам опрашивает   ┌─────────────────────────────────────────────────────────┐
│   GitLab     │ ◄─────────────────────── │ gitlab-runner (shell, тег neyasiti-deploy)              │
└──────────────┘                          │   check → build → system → deploy → verify              │
                                          │                                                         │
Интернет ──► :80/:443 ──────────────────► │ caddy ─caddy_net─► cucumberbot-web (nginx) ─► backend   │
                                          │                                     │        ├─► db     │
                                          │                                     │        └─► minio  │
                                          └─────────────────────────────────────┼───────────────────┘
                                                                                │ ws://…:9090 (VPN)
                                                                          робот: rosbridge_server + Nav2
```

- Наружу открыт только Caddy (80/443). Сервисы стека портов не публикуют; консоль MinIO
  доступна только на `127.0.0.1:19001` сервера.
- Данные лежат в docker-томах `cucumberbot_postgres_data` и `cucumberbot_minio_data` и переживают
  передеплой.
- Секреты хранятся в GitLab в CI/CD-переменной `CUCUMBERBOT_ENV`. Постоянная папка на сервере не нужна.

## Пайплайн

| Стадия | Job | Что проверяет | Когда |
|---|---|---|---|
| check | `check:backend` | `ruff` и юнит-тесты, выполняются внутри `docker build --target test` | MR, main |
| check | `check:frontend` | `tsc` и сборка Vite | MR, main |
| build | `build:images` | образы `cucumberbot-backend:<sha>`, `cucumberbot-frontend:<sha>` и `cucumberbot-ros2:ci` | MR, main |
| system | `system:tests` | изолированный стек и ROS 2 Humble, подробности ниже | MR, main |
| deploy | `deploy:production` | `docker compose up --wait`: job падает, если сервис не стал healthy | main |
| verify | `verify:internal` | путь Caddy → nginx → backend внутри `caddy_net` | main |
| verify | `verify:public` | `https://cutecumber.neyasyti.ru` снаружи (DNS + TLS); `allow_failure`, пока не настроены шаги 1 и 5 | main |

Что делает `system:tests` (отдельный compose-проект `cucumberbot-ci-<pipeline id>`, после job он удаляется вместе с томами):
1. Откатывает миграции Alembic до нуля и применяет их заново.
2. Проверяет API через nginx: логин, авторизацию, карту из редактора, валидацию и экспорт для Nav2, QR-метки (sync, PNG, PDF, landmarks.yaml).
3. Работает с ROS 2 через настоящий `rosbridge_server` (Humble). `/map` доходит как корректный
   `nav_msgs/msg/OccupancyGrid`, `/amcl_pose` попадает в `GET /api/v1/robot/pose`.
4. Загружает экспортированные `map.pgm` и `map.yaml` штатным `nav2_map_server` (configure → activate)
   и сверяет размеры опубликованной карты.

Отчёт JUnit отображается в MR. Лог backend и `map.zip` сохраняются в артефактах job.

---

## 0. Репозиторий в GitLab

`origin` указывает на GitHub, а runner работает с `git.neyasyti.ru`. Код зеркалируется во второй
remote — проект `neyasyti-aero/cucumberbot-web-panel` уже создан в GitLab:

```bash
git remote add gitlab https://git.neyasyti.ru/neyasyti-aero/cucumberbot-web-panel.git
git push gitlab main
```

GitHub можно оставить зеркалом или убрать. В репозитории больше нет `.github/workflows`, весь CI/CD собран в `.gitlab-ci.yml`.

## 1. DNS

| Тип | Имя | Значение |
|-----|-----|----------|
| A   | cutecumber | `77.50.187.110` |

Регистр в DNS-имени не важен: `CUTECUMBER.neyasyti.ru` и `cutecumber.neyasyti.ru` — один и тот же адрес.
Проверка: `dig +short cutecumber.neyasyti.ru` → `77.50.187.110`.

## 2. Runner

На сервере уже работает runner сайта с тегом `neyasiti-deploy`. Его достаточно включить для нового проекта:

**cucumberbot-web-panel → Settings → CI/CD → Runners → Project runners → Enable** у runner'а `neyasiti-deploy`
(нужна роль Maintainer в обоих проектах).

Если отдельный runner удобнее, зарегистрируйте его по `website/deploy/README.md` (шаг 2) с тем же
тегом. При `concurrent = 1` пайплайны сайта и панели выполняются по очереди, так и задумано.

Проверить версию compose на сервере (нужна ≥ 2.24 для `!reset`/`!override` в compose-файлах):

```bash
docker compose version
```

> ⚠️ Ветка `main` должна быть **protected** (Settings → Repository → Protected branches), push/merge
> только у Maintainers. Runner в группе `docker` фактически имеет права root на сервере.

## 3. Секреты: переменная `CUCUMBERBOT_ENV`

**Settings → CI/CD → Variables → Add variable:**
- Type: **File**
- Key: `CUCUMBERBOT_ENV`
- Flags: **Protected** (доступна только в `main`)
- Value: содержимое по шаблону [`docker/.env.example`](../docker/.env.example) с боевыми значениями:

```dotenv
DB_PASSWORD=<openssl rand -hex 24>
JWT_SECRET=<openssl rand -hex 32>
MINIO_ACCESS_KEY=cucumberbot
MINIO_SECRET_KEY=<openssl rand -hex 24>
ADMIN_EMAIL=admin@neyasyti.ru
ADMIN_PASSWORD=<временный пароль, сменить после первого входа>
ROSBRIDGE_URL=ws://<адрес робота в VPN>:9090
ROS_ODOM_TOPIC=/odom
ROS_POSE_TOPIC=/amcl_pose
ROS_SIMULATION=false
CORS_ORIGINS=https://cutecumber.neyasyti.ru
DEBUG=false
MINIO_CONSOLE_PORT=19001
```

`DB_PASSWORD` и `MINIO_*` применяются только при **первом** создании томов. Если поменять их позже,
сервисы не смогут подключиться к уже созданным данным.

## 4. Первый деплой

Запустите **Build → Pipelines → Run pipeline** на `main` или сделайте push. Первый прогон
длится дольше обычного (несколько минут), потому что собирается образ ROS 2. Дальше он берётся из кэша docker.

Проверка на сервере:

```bash
docker ps --filter name=cucumberbot-                         # все сервисы (healthy)
docker exec caddy wget -qO- http://cucumberbot-web/api/v1/health
# {"status":"ok","robot_connected":true|false}
```

Контейнер `cucumberbot-web` должен быть запущен **до** правки Caddy, иначе Caddy не найдёт это имя.

## 5. Домен в Caddy

Caddyfile общий для сервера, правку согласуйте с тем, кто его ведёт.

```bash
# 1) положить блок (домен уже прописан)
sudo cp deploy/caddy/cucumberbot.conf /home/fallback/caddy/

# 2) добавить в конец /home/fallback/caddy/Caddyfile:
#    import /etc/caddy/cucumberbot.conf

# 3) проверить конфиг: при ошибке не поднимутся ВСЕ сайты сервера
docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

# 4) применить (admin off → только перезапуск, сайты пропадут на пару секунд)
docker restart caddy
```

Проверка: `curl -I https://cutecumber.neyasyti.ru` → 200. После этого job `verify:public` станет зелёным.

## 6. После запуска

1. Войдите под `ADMIN_EMAIL` и **смените пароль** администратора.
2. Создайте операторов в админке и не работайте под admin.

## 7. Связь с роботом

Backend сам подключается к `rosbridge_server` робота по `ROSBRIDGE_URL` и переподключается
каждые 5 с. Статус соединения показывает поле `robot_connected` в `/api/v1/health`.

- **Сеть.** Сервер должен достучаться до робота на порт 9090. Робот в теплице обычно за NAT,
  поэтому нужен VPN (WireGuard/Tailscale) или туннель. У rosbridge **нет авторизации**:
  не публикуйте 9090 в интернет.
- **На роботе (ROS 2):** `rosbridge_server`, Nav2 с AMCL (поза в `/amcl_pose`, кадр `map`), `/odom`,
  `/battery_state`, `/task_status`.
- **Карта.** Есть два варианта, выберите один:
  - скачать в редакторе «Для Nav2» (`map.pgm` + `map.yaml`) и указать `yaml_filename` в `map_server`;
  - отправить из веба (`POST /api/v1/maps/{id}/publish` → `/map`, transient local). В этом случае
    `map_server` на роботе не запускают, иначе два издателя `/map` будут перетирать друг друга.
- **Кадр координат.** Угол помещения в редакторе — это `(0, 0)` кадра `map`, x вправо, y вверх (REP-103).
  В этих же координатах заданы QR-метки (`landmarks.yaml`) и поза из `GET /api/v1/robot/pose`.

## Повседневная работа

- **Merge request** → check, build, system (без выкатки)
- **Merge в main** → то же, затем deploy и verify
- **Откат:** Operate → Environments → production → «Rollback» (образы 5 последних коммитов
  хранятся на сервере). Вручную, из любой копии репозитория на сервере:
  ```bash
  docker images cucumberbot-backend
  IMAGE_TAG=<sha> docker compose -p cucumberbot -f docker/docker-compose.yml \
      -f docker/docker-compose.server.yml --env-file /path/to/env up -d --no-build --wait
  ```
  ⚠️ Если новая версия применила миграцию БД, перед откатом кода сделайте `alembic downgrade`.
- **Логи:** `docker logs -f cucumberbot-backend-1`, `docker logs cucumberbot-frontend-1`, `docker logs caddy`
- **Консоль MinIO:** `ssh -L 19001:127.0.0.1:19001 <server>` → http://localhost:19001

### Резервные копии

```bash
# PostgreSQL
docker exec cucumberbot-db-1 pg_dump -U postgres cucumberbot | gzip > cucumberbot_$(date +%F).sql.gz
# MinIO (карты, подложки, QR)
docker run --rm -v cucumberbot_minio_data:/data -v "$PWD":/backup alpine \
    tar czf /backup/cucumberbot_minio_$(date +%F).tgz -C /data .
```

## Если что-то не так

| Симптом | Причина |
|---|---|
| job висит в `pending` | runner не включён для проекта или offline: `sudo gitlab-runner verify` |
| `Не задана CI/CD-переменная CUCUMBERBOT_ENV` | переменной нет, она не типа File или не Protected, а ветка не protected |
| `required variable … is missing a value` | в `CUCUMBERBOT_ENV` не хватает строки, см. шаг 3 |
| `yaml: unknown tag !reset` | на сервере старый docker compose, нужен ≥ 2.24 |
| `network caddy_net … could not be found` | Caddy пересоздан с другой сетью: `docker network ls` |
| deploy упал на `--wait` | сервис не стал healthy: `docker logs cucumberbot-backend-1` (миграции, пароль БД) |
| 502 на домене | `cucumberbot-web` не запущен или не в `caddy_net` |
| нет HTTPS, ошибка ACME в логах Caddy | DNS ещё не обновился или не указывает на 77.50.187.110 |
| `robot_connected: false` | робот недоступен по `ROSBRIDGE_URL`: VPN, адрес, запущен ли rosbridge |
| `system:tests` упал на `check_nav2_map.sh` | карта не грузится в Nav2: смотрите вывод job и артефакт `map.zip` |
