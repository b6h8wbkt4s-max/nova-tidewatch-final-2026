# -*- coding: utf-8 -*-
"""D5 固定规则 / ML 对照：
- 用 pandas 读 data/tidewatch_history.csv（自动修复行粘连，不改原文件）
- 每个断面独立训练 IsolationForest（特征：waterLevel, turbidity, flowLevel）
- 对历史每条 + 构造样本输出 ML 标签（明显异常 / 偏离历史 / 略偏 / 接近历史）
- 汇总写入 report/d5_compare.json，供 Web 端对照显示
"""
import io
import json
import os
import re
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, "data", "tidewatch_history.csv")
OUT_PATH = os.path.join(BASE, "web", "d5_compare.json")

RULE_WEIGHT = 0.7
ML_WEIGHT = 0.3

# 判级规则：与 contract 一致，status 只能由规则计算，不能手填
def rule_status(waterLevel, turbidity):
    if waterLevel >= 8.5:
        return "洪水预警"
    elif waterLevel >= 7.0:
        return "高水位警戒"
    elif turbidity >= 60:
        return "水质浑浊"
    return "正常"

# ML 标签定义（固定规则，统一应用于所有数据，不做事后调参）：
#   明显异常 = 模型投票判异常（predict=-1）且 decision_function 分数 < 0
#   偏离历史 = 未到投票线但分数 < 0（低于典型历史形态）
#   略偏     = 0 <= 分数 < 0.1
#   接近历史 = 分数 >= 0.1
def ml_label(score, pred):
    if pred == -1 and score < 0:
        return "明显异常"
    if score < 0:
        return "偏离历史"
    if score < 0.1:
        return "略偏"
    return "接近历史"

ML_ABNORMAL = {"明显异常", "偏离历史"}

def is_consistent(status_rule, status_ml):
    """规则判异常 与 ML 判异常 是否一致（略偏按不异常算）"""
    return (status_rule != "正常") == (status_ml in ML_ABNORMAL)

# 构造样本：保证至少 1 个"值得分析"的不一致案例，不参与训练，逐条标注
CONSTRUCTED = [
    {
        "reachId": "reach-a", "waterLevel": 6.8, "turbidity": 45.0, "flowLevel": 2,
        "time": "2026-10-04 19:00:00",
        "case_note": "构造样本①：规则判正常（水位<7 且浊度<60），ML 判明显异常——水位/浊度同时偏离 reach-a 历史形态（4.5~5.0 m / 20~25 NTU），按 contract 8.3 需人工复核",
    },
    {
        "reachId": "reach-b", "waterLevel": 9.2, "turbidity": 20.0, "flowLevel": 2,
        "time": "2026-10-04 19:05:00",
        "case_note": "构造样本②：规则判洪水预警，ML 判略偏——与历史洪水水位（9.0 m）同形态，模型把反复出现的历史洪水学成了常态，需人工复核",
    },
]

def load_history():
    with open(CSV_PATH, encoding="utf-8") as f:
        raw = f.read()
    # 数据质量修复：手写历史末尾无换行时，追加行会与上一行粘连（时间戳后直接跟 reach-）
    fixed = re.sub(r"(\d{2}:\d{2}:\d{2})(reach-)", r"\1\n\2", raw)
    if fixed != raw:
        print("检测到 CSV 行粘连，已自动修复（不改原文件）")
    return pd.read_csv(io.StringIO(fixed))

def main():
    df = load_history()

    # 每个断面独立训练，避免跨断面形态互相污染
    models = {}
    for reachId, g in df.groupby("reachId"):
        X = g[["waterLevel", "turbidity", "flowLevel"]].to_numpy(dtype=float)
        if len(X) < 2:
            print(f"{reachId} 样本不足，跳过训练")
            continue
        model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        model.fit(X)
        models[reachId] = model
        print(f"{reachId}: 训练样本 {len(X)} 条")

    def predict(reachId, waterLevel, turbidity, flowLevel):
        model = models.get(reachId)
        if model is None:
            return None, None
        X = np.array([[waterLevel, turbidity, flowLevel]], dtype=float)
        score = float(model.decision_function(X)[0])
        pred = int(model.predict(X)[0])
        return ml_label(score, pred), round(score, 3)

    records = []
    # 历史每条：status_rule 由规则重算（与 CSV 的 status 对照，不一致说明数据被改过）
    mismatch = 0
    for _, row in df.iterrows():
        sr = rule_status(row["waterLevel"], row["turbidity"])
        if sr != row["status"]:
            mismatch += 1
        sm, score = predict(row["reachId"], row["waterLevel"], row["turbidity"], row["flowLevel"])
        records.append({
            "reachId": row["reachId"],
            "waterLevel": float(row["waterLevel"]),
            "turbidity": float(row["turbidity"]),
            "flowLevel": int(row["flowLevel"]),
            "status_rule": sr,
            "status_ml": sm,
            "anomaly_score": score,
            "is_consistent": None if sm is None else is_consistent(sr, sm),
            "constructed": False,
            "case_note": None,
            "time": row["time"],
        })
    if mismatch:
        print(f"警告：{mismatch} 条 CSV status 与规则重算不一致")

    # 构造样本（不参与训练，仅用训练好的模型预测）
    for c in CONSTRUCTED:
        sr = rule_status(c["waterLevel"], c["turbidity"])
        sm, score = predict(c["reachId"], c["waterLevel"], c["turbidity"], c["flowLevel"])
        records.append({
            "reachId": c["reachId"],
            "waterLevel": c["waterLevel"],
            "turbidity": c["turbidity"],
            "flowLevel": c["flowLevel"],
            "status_rule": sr,
            "status_ml": sm,
            "anomaly_score": score,
            "is_consistent": None if sm is None else is_consistent(sr, sm),
            "constructed": True,
            "case_note": c["case_note"],
            "time": c["time"],
        })

    valid = [r for r in records if r["is_consistent"] is not None]
    summary = {
        "total": len(records),
        "consistent": sum(1 for r in valid if r["is_consistent"]),
        "inconsistent": sum(1 for r in valid if not r["is_consistent"]),
        "constructed": sum(1 for r in records if r["constructed"]),
    }
    out = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "IsolationForest per reach; features=[waterLevel, turbidity, flowLevel]; contamination=0.1; random_state=42",
        "rule_weight": RULE_WEIGHT,
        "ml_weight": ML_WEIGHT,
        "labels": ["明显异常", "偏离历史", "略偏", "接近历史"],
        "summary": summary,
        "records": records,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"写入 {OUT_PATH}")
    print(f"共 {summary['total']} 条（构造 {summary['constructed']}），一致 {summary['consistent']}，不一致 {summary['inconsistent']}")
    for r in records:
        if r["is_consistent"] is False:
            note = r["case_note"] or "自然数据"
            print(f"  不一致: {r['reachId']} 水位{r['waterLevel']} 浊度{r['turbidity']} "
                  f"规则[{r['status_rule']}] ML[{r['status_ml']}] ({note})")

if __name__ == "__main__":
    main()
