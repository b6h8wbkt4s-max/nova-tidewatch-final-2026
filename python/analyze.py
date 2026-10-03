import pandas as pd
import matplotlib.pyplot as plt
import os

# 中文字体设置（Windows）
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, 'data', 'tidewatch_history.csv')
REPORT_DIR = os.path.join(BASE, 'report')
IMG_DIR = os.path.join(REPORT_DIR, 'img')
os.makedirs(IMG_DIR, exist_ok=True)

# 1. 读 CSV
df = pd.read_csv(CSV_PATH)
df['time'] = pd.to_datetime(df['time'])

# 2. 按断面统计
summary = df.groupby('reachId').agg(
    count=('waterLevel', 'count'),
    waterLevel_mean=('waterLevel', 'mean'),
    waterLevel_max=('waterLevel', 'max'),
    turbidity_mean=('turbidity', 'mean'),
    turbidity_max=('turbidity', 'max'),
    abnormal_count=('status', lambda s: (s != '正常').sum())
).reset_index()

# 3. 按断面画水位趋势
plt.figure(figsize=(8, 4))
for reach in df['reachId'].unique():
    sub = df[df['reachId'] == reach].sort_values('time')
    plt.plot(sub['time'], sub['waterLevel'], marker='o', label=reach)
plt.axhline(y=8.5, color='r', linestyle='--', label='洪水预警线 8.5')
plt.axhline(y=7.0, color='orange', linestyle='--', label='高水位警戒线 7.0')
plt.xlabel('时间')
plt.ylabel('水位')
plt.title('各断面水位趋势')
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(IMG_DIR, 'water_level_trend.png'))
plt.close()

# 4. 按断面画浊度趋势
plt.figure(figsize=(8, 4))
for reach in df['reachId'].unique():
    sub = df[df['reachId'] == reach].sort_values('time')
    plt.plot(sub['time'], sub['turbidity'], marker='o', label=reach)
plt.axhline(y=60, color='purple', linestyle='--', label='水质浑浊线 60')
plt.xlabel('时间')
plt.ylabel('浊度')
plt.title('各断面浊度趋势')
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(IMG_DIR, 'turbidity_trend.png'))
plt.close()

# 5. 生成 report.html
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>TideWatch 离线分析报告</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; margin: 40px; }}
table {{ border-collapse: collapse; margin: 20px 0; }}
th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: center; }}
th {{ background: #f0f0f0; }}
img {{ max-width: 900px; display: block; margin: 20px 0; }}
</style>
</head>
<body>
<h1>TideWatch 离线分析报告</h1>
<p>数据来源：data/tidewatch_history.csv（模拟运行数据）</p>
<p>生成时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<h2>一、按断面统计</h2>
{summary.to_html(index=False)}

<h2>二、水位趋势</h2>
<img src="img/water_level_trend.png" alt="水位趋势">

<h2>三、浊度趋势</h2>
<img src="img/turbidity_trend.png" alt="浊度趋势">

<h2>四、说明</h2>
<ul>
<li>本报告由 python/analyze.py 自动生成，请勿手工修改。</li>
<li>判级规则：waterLevel>=8.5 洪水预警；否则>=7.0 高水位警戒；否则 turbidity>=60 水质浑浊；否则正常。</li>
<li>数据为模拟运行数据，不代表真实水文情况。</li>
</ul>
</body>
</html>
"""

with open(os.path.join(REPORT_DIR, 'report.html'), 'w', encoding='utf-8') as f:
    f.write(html)

print('分析完成，报告已生成：report/report.html')