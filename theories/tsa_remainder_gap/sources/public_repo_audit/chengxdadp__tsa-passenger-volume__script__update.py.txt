#!/usr/bin/env python3
"""
TSA客流量数据更新脚本

使用方法:
  python update.py                  # 抓取当前年份数据，生成图表和报告
  python update.py --year 2025      # 补录指定年份数据，生成图表和报告
  python update.py --charts-only    # 不抓取数据，仅用现有数据库重新生成图表和报告
"""

import argparse
import os
import sys
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from data_scraper import (
    scrape_latest_data, scrape_year_data, load_historical_data, save_data,
    init_db, migrate_pkl_to_sqlite, get_db_path
)
from data_processor import prepare_data_for_visualization
from visualization import (
    create_7day_moving_average_chart,
    create_yearly_comparison_chart,
    create_monthly_trend_chart,
    create_recent_years_chart,
)
from statistics import generate_comprehensive_statistics, print_statistics_report, update_readme


def ensure_database():
    """确保数据库已就绪。若不存在则自动从pkl文件迁移。"""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print("数据库不存在，开始从pkl文件迁移历史数据...")
        migrate_pkl_to_sqlite()
    else:
        init_db()


def run_pipeline(all_data, current_year, chart_dir):
    """数据处理 → 图表 → 统计报告（公共流程）"""
    print(f"\n已加载数据年份: {sorted(all_data.keys())}")
    for year, data in sorted(all_data.items()):
        print(f"  {year}年: {len(data)} 条记录")

    # 数据处理
    print("\n步骤: 处理数据...")
    processed_data = prepare_data_for_visualization(all_data)

    # 图表
    print("\n步骤: 生成可视化图表...")
    os.makedirs(chart_dir, exist_ok=True)
    create_7day_moving_average_chart(processed_data, chart_dir)
    create_yearly_comparison_chart(processed_data, chart_dir)
    create_monthly_trend_chart(processed_data, chart_dir)
    create_recent_years_chart(processed_data, chart_dir)
    print("所有图表已生成!")

    # 统计报告
    print("\n步骤: 生成统计报告...")
    try:
        stats = generate_comprehensive_statistics(all_data, current_year)
        readme_path = os.path.join(os.path.dirname(current_dir), 'README.md')
        update_readme(stats, readme_path)
        print_statistics_report(stats)
    except Exception as e:
        print(f"统计报告生成失败: {e}")


def mode_default(chart_dir):
    """默认模式：抓取当前年份数据"""
    print("\n[模式] 抓取当前年份最新数据")

    print("\n步骤1: 抓取最新数据...")
    latest_data = scrape_latest_data()
    current_year = str(latest_data['Date'].max().year)
    print(f"获取 {len(latest_data)} 条记录，数据截至 {latest_data['Date'].max().date()}")

    print(f"\n步骤2: 保存 {current_year} 年数据...")
    save_data(latest_data, current_year)

    print("\n步骤3: 加载历史数据...")
    all_data = load_historical_data(exclude_year=current_year)
    all_data[current_year] = latest_data

    run_pipeline(all_data, current_year, chart_dir)
    return current_year


def mode_backfill(year, chart_dir):
    """补录模式：抓取指定年份历史数据"""
    year_str = str(year)
    print(f"\n[模式] 补录 {year_str} 年历史数据")

    print(f"\n步骤1: 从TSA官网抓取 {year_str} 年数据...")
    data = scrape_year_data(year_str)
    print(f"获取 {len(data)} 条记录，数据范围 {data['Date'].min().date()} 至 {data['Date'].max().date()}")

    print(f"\n步骤2: 保存 {year_str} 年数据到数据库...")
    save_data(data, year_str)

    print("\n步骤3: 加载所有年份数据...")
    all_data = load_historical_data()  # 包含刚保存的year_str

    # 以数据库中最新年份作为统计基准年
    current_year = max(all_data.keys())
    run_pipeline(all_data, current_year, chart_dir)
    return year_str


def mode_charts_only(chart_dir):
    """仅生成图表模式：不抓取任何数据"""
    print("\n[模式] 仅重新生成图表和报告（使用现有数据库）")

    print("\n步骤1: 加载所有年份数据...")
    all_data = load_historical_data()
    if not all_data:
        print("数据库中暂无数据，请先运行 update.py 或 update.py --year YEAR")
        sys.exit(1)

    current_year = max(all_data.keys())
    run_pipeline(all_data, current_year, chart_dir)
    return current_year


def main():
    parser = argparse.ArgumentParser(
        description='TSA旅客安检量数据更新工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python update.py                  抓取当前年份，生成图表和报告
  python update.py --year 2025      补录2025年历史数据，重新生成图表
  python update.py --charts-only    不联网，仅用现有数据库重新生成图表
        """
    )
    parser.add_argument(
        '--year', type=int, default=None,
        metavar='YEAR',
        help='补录指定年份数据（如 --year 2025）'
    )
    parser.add_argument(
        '--charts-only', action='store_true',
        help='不抓取数据，仅用现有数据库重新生成图表和报告'
    )
    args = parser.parse_args()

    print("=" * 60)
    print("TSA客流量数据更新脚本")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    chart_dir = os.path.join(os.path.dirname(current_dir), 'chart')

    try:
        print("\n初始化数据库...")
        ensure_database()

        if args.charts_only:
            target_year = mode_charts_only(chart_dir)
        elif args.year is not None:
            target_year = mode_backfill(args.year, chart_dir)
        else:
            target_year = mode_default(chart_dir)

        print("\n" + "=" * 60)
        print("完成!")
        print(f"图表/报告: {chart_dir}")
        print(f"数据库:    {get_db_path()}")
        print("=" * 60)

    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
