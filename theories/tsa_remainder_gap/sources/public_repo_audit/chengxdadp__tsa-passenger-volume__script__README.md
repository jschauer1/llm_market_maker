# script/ 模块说明

各 Python 模块的详细接口文档。日常使用请参考根目录的 [README.md](../README.md)。

---

## 模块概览

| 文件 | 职责 |
|------|------|
| `update.py` | 主入口：串联所有步骤 |
| `test_update.py` | 仅测试统计，不联网 |
| `data_scraper.py` | 网络抓取 + SQLite 读写 |
| `data_processor.py` | DataFrame 转换（7日均线、排序键） |
| `visualization.py` | 生成并保存三张 PNG 图表 |
| `statistics.py` | 增长率计算 + Markdown 报告 |

---

## data_scraper.py

### 数据库操作

```python
from data_scraper import get_db_path, init_db

print(get_db_path())   # .../data/tsa_data.db
init_db()              # 创建 data/ 目录和 passenger_data 表（幂等）
```

### 抓取数据

```python
from data_scraper import scrape_latest_data, scrape_year_data

df = scrape_latest_data()        # 抓取当前页面（最新年份）
df = scrape_year_data(2023)      # 抓取指定年份
# 返回 DataFrame: columns=['Date', 'Passenger_Numbers']
```

### 读写历史数据

```python
from data_scraper import load_historical_data, save_data

# 加载所有年份（排除当前年份，以新抓取数据为准）
data_dict = load_historical_data(exclude_year='2026')
# 返回 {'2023': df, '2024': df, '2025': df, ...}

# 写入/更新数据（INSERT OR REPLACE）
save_data(df, year=2026)
```

### 从旧 pkl 文件迁移（一次性）

```python
from data_scraper import migrate_pkl_to_sqlite
migrate_pkl_to_sqlite()   # 自动搜索并导入所有 passenger_data_YYYY.pkl
```

---

## data_processor.py

```python
from data_processor import (
    prepare_data_for_visualization,
    get_same_period_data,
    filter_data_by_month_range,
)

# 添加 month_day、sort_key、7day_avg 列
processed = prepare_data_for_visualization(data_dict)

# 获取与参考数据相同时间段的对比数据
same_period = get_same_period_data(reference_df, comparison_df)

# 按月份区间过滤
jan_jun = filter_data_by_month_range(df, start_month=1, end_month=6)
```

---

## visualization.py

生成图表并保存到指定目录（默认 `../chart`），不阻塞（使用 `plt.close()` 而非 `plt.show()`）。

```python
from visualization import (
    create_7day_moving_average_chart,
    create_yearly_comparison_chart,
    create_monthly_trend_chart,
)

create_7day_moving_average_chart(processed_data, output_dir='../chart')
create_yearly_comparison_chart(processed_data, output_dir='../chart')
create_monthly_trend_chart(processed_data, output_dir='../chart')
```

| 函数 | 输出文件 | 图表类型 |
|------|----------|----------|
| `create_7day_moving_average_chart` | `tsa_7day_moving_average.png` | 折线图，7日均线 |
| `create_yearly_comparison_chart` | `tsa_yearly_comparison.png` | 散点图，原始日数据 |
| `create_monthly_trend_chart` | `tsa_monthly_trend.png` | 折线图，月均值 |

---

## statistics.py

```python
from statistics import (
    generate_comprehensive_statistics,
    print_statistics_report,
    generate_markdown_report,
)

# current_year 默认取当前系统年份
stats = generate_comprehensive_statistics(data_dict, current_year='2026')

print_statistics_report(stats)                       # 打印到控制台
report_path = generate_markdown_report(stats, '../chart')  # 写 Markdown 文件
```

**统计内容**：

- `basic_stats`：各年份记录数、总客流、日均客流、数据范围
- `ytd_growth`：当前年 YTD vs 各历史年同期增长率
- `period_growth`：1–6 月、7–12 月分时段增长率

---

## 各模块独立运行（调试）

每个模块均可直接 `python <module>.py` 运行，内置测试逻辑从 SQLite 加载数据：

```bash
python data_scraper.py    # 抓取最新数据并打印前几行
python data_processor.py  # 处理数据并打印记录数
python visualization.py   # 生成三张图表
python statistics.py      # 生成并打印统计报告
python test_update.py     # 完整统计流程（不联网）
```
