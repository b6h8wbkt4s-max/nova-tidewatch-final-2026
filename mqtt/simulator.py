import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime

BROKER = "localhost"
PORT = 1883
TOPIC = "tidewatch/reach-a/state"

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

samples = [
    (4.5, 20, 0),
    (5.0, 25, 1),
    (7.6, 20, 1),
    (9.0, 20, 2),
    (4.5, 75, 1),
]

try:
    for waterLevel, turbidity, flowLevel in samples:
        payload = {
            "reachId": "reach-a",
            "waterLevel": waterLevel,
            "turbidity": turbidity,
            "flowLevel": flowLevel,
            "status": make_status(waterLevel, turbidity),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        client.publish(TOPIC, json.dumps(payload, ensure_ascii=False))
        print("published:", payload)
        time.sleep(3)
finally:
    client.loop_stop()
    client.disconnect()