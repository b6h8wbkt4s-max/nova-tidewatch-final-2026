import paho.mqtt.client as mqtt
import json
import time
import csv
import os
from datetime import datetime

BROKER = "localhost"
PORT = 1883
TOPIC_TEMPLATE = "tidewatch/{reachId}/state"

# D5 历史数据：每条 MQTT 消息同时追加到 data/tidewatch_history.csv
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "tidewatch_history.csv")
CSV_FIELDS = ["reachId", "waterLevel", "turbidity", "flowLevel", "status", "time"]

client = mqtt.Client()
client.connect(BROKER, PORT, 60)
client.loop_start()

def make_status(waterLevel, turbidity):
    if waterLevel >= 8.5:
        return "洪水预警"
    elif waterLevel >= 7.0:
        return "高水位警戒"
    elif turbidity >= 60:
        return "水质浑浊"
    else:
        return "正常"

# 三个断面各 3 条：(waterLevel, turbidity, flowLevel)
# 第 1 条为 contract.md 第 3 节演示数据，后 2 条变化以观察状态转移
samples_by_reach = {
    "reach-a": [
        (4.5, 20, 0),   # 正常
        (5.0, 25, 0),   # 正常
        (7.6, 20, 1),   # 高水位警戒
    ],
    "reach-b": [
        (9.0, 20, 2),   # 洪水预警
        (7.8, 20, 2),   # 高水位警戒
        (6.5, 20, 1),   # 正常
    ],
    "reach-c": [
        (4.5, 75, 1),   # 水质浑浊
        (4.6, 68, 1),   # 水质浑浊
        (4.7, 55, 1),   # 正常
    ],
}

def append_history(payload):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    # 表头只写一次：文件不存在或为空时先写表头
    exists = os.path.exists(CSV_PATH) and os.path.getsize(CSV_PATH) > 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: payload[k] for k in CSV_FIELDS})

def publish_reach(reachId, waterLevel, turbidity, flowLevel):
    payload = {
        "reachId": reachId,
        "waterLevel": waterLevel,
        "turbidity": turbidity,
        "flowLevel": flowLevel,
        "status": make_status(waterLevel, turbidity),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    topic = TOPIC_TEMPLATE.format(reachId=reachId)
    client.publish(topic, json.dumps(payload, ensure_ascii=False))
    append_history(payload)
    print("published:", payload)

try:
    # 按轮次发布：每轮 3 个断面各发 1 条，共 3 轮
    for round_i in range(3):
        for reachId, samples in samples_by_reach.items():
            waterLevel, turbidity, flowLevel = samples[round_i]
            publish_reach(reachId, waterLevel, turbidity, flowLevel)
            time.sleep(3)
finally:
    client.loop_stop()
    client.disconnect()
