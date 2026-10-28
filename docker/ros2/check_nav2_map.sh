#!/usr/bin/env bash
# Загружает map.pgm + map.yaml штатным nav2_map_server и проверяет, что карта
# опубликована в /map с ожидаемыми размерами.
#   check_nav2_map.sh /path/to/map.zip
# setup.bash обращается к неопределённым переменным — подключаем до set -u
source /opt/ros/humble/setup.bash
set -euo pipefail

ZIP=${1:?usage: check_nav2_map.sh map.zip}
DIR=$(mktemp -d)
python3 -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$ZIP" "$DIR"

read -r EXPECTED_W EXPECTED_H < <(python3 - "$DIR/map.pgm" <<'PY'
import sys
tokens = []
with open(sys.argv[1], "rb") as f:
    for line in f:
        if line.startswith(b"#"):
            continue
        tokens += line.split()
        if len(tokens) >= 3:
            break
print(int(tokens[1]), int(tokens[2]))
PY
)

# Бинарник напрямую (не `ros2 run`): иначе kill не останавливает дочерний процесс узла
NODE=check_map_server_$$
TOPIC=/check_map_$$
/opt/ros/humble/lib/nav2_map_server/map_server --ros-args -r __node:=$NODE     -p yaml_filename:="$DIR/map.yaml" -p topic_name:=$TOPIC >/tmp/$NODE.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
    ros2 lifecycle get /$NODE >/dev/null 2>&1 && break
    sleep 0.5
done

# configure читает yaml и pgm — при некорректной карте переход не выполнится
for transition in configure activate; do
    ros2 lifecycle set /$NODE $transition | grep -q "Transitioning successful"         || { echo "map_server: $transition не прошёл"; cat /tmp/$NODE.log; exit 1; }
done

INFO=$(timeout 30 ros2 topic echo $TOPIC nav_msgs/msg/OccupancyGrid --once     --qos-durability transient_local --qos-reliability reliable --field info)
W=$(echo "$INFO" | awk '/^width:/ {print $2}')
H=$(echo "$INFO" | awk '/^height:/ {print $2}')

if [ "$W" != "$EXPECTED_W" ] || [ "$H" != "$EXPECTED_H" ]; then
    echo "Размер карты в Nav2 ${W}x${H}, ожидался ${EXPECTED_W}x${EXPECTED_H}"
    exit 1
fi
echo "nav2_map_server: карта ${W}x${H} загружена и опубликована"
