# ROS 2 Humble с rosbridge и nav2_map_server — для системных тестов в CI и профиля demo.
# Повторяет то, что запущено на роботе: rosbridge_server (:9090) и map_server из Nav2.
FROM ros:humble-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-rosbridge-server \
        ros-humble-nav2-map-server \
        ros-humble-nav2-lifecycle-manager \
    && rm -rf /var/lib/apt/lists/*

COPY check_nav2_map.sh /usr/local/bin/check_nav2_map.sh
RUN chmod +x /usr/local/bin/check_nav2_map.sh

EXPOSE 9090
HEALTHCHECK --interval=5s --timeout=3s --start-period=20s --retries=10 \
    CMD bash -c 'echo > /dev/tcp/127.0.0.1/9090' || exit 1

CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml"]
