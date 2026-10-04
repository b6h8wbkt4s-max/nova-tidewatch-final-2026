数据：data/tidewatch\_history.csv，74 条



方法：IsolationForest per reach



参数：features=\[waterLevel, turbidity, flowLevel]; contamination=0.1; random\_state=42



两个不一致案例：



构造样本①：reach-a 6.8/45/flow2，规则\[正常] ML\[明显异常]



构造样本②：reach-b 9.2/20/flow2，规则\[洪水预警] ML\[略偏]



组合裁决：规则 0.7 / ML 0.3





