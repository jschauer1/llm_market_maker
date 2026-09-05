import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import os
from glob import glob


def get_db_path():
    """返回SQLite数据库的绝对路径（位于 data/ 子目录）"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    return os.path.join(project_root, 'data', 'tsa_data.db')


def init_db():
    """初始化数据库，创建 data/ 目录和表结构（幂等操作）"""
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS passenger_data (
            date TEXT PRIMARY KEY,
            passengers INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def scrape_tsa_passenger_data(url):
    """
    从TSA网站抓取每日旅客流量数据并返回pandas DataFrame

    参数:
    url: TSA数据页面的URL
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')

    table = soup.find('table')

    if not table:
        raise ValueError("未找到数据表格")

    rows = table.find('tbody').find_all('tr')

    data = []
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 2:
            date = cells[0].get_text().strip()
            number_text = cells[1].get_text().strip()
            number = int(number_text.replace(',', ''))
            data.append((date, number))

    df = pd.DataFrame(data, columns=['Date', 'Passenger_Numbers'])

    df['Date'] = pd.to_datetime(df['Date'])

    df = df.sort_values('Date', ascending=False).reset_index(drop=True)

    return df


def scrape_latest_data():
    """抓取最新年份的数据"""
    url = 'https://www.tsa.gov/travel/passenger-volumes'
    return scrape_tsa_passenger_data(url)


def scrape_year_data(year):
    """抓取指定年份的数据"""
    url = f"https://www.tsa.gov/travel/passenger-volumes/{year}"
    return scrape_tsa_passenger_data(url)


def load_historical_data(exclude_year=None):
    """
    从SQLite数据库读取所有历史数据

    参数:
    exclude_year: 排除的年份字符串（通常是当前年份，因为会单独从网络抓取）

    返回:
    字典: {year_str: DataFrame}，按年份升序排列
    """
    db_path = get_db_path()

    if not os.path.exists(db_path):
        print("数据库文件不存在，请先运行数据迁移或抓取数据")
        return {}

    conn = sqlite3.connect(db_path)

    years_df = pd.read_sql_query(
        "SELECT DISTINCT strftime('%Y', date) AS year FROM passenger_data ORDER BY year",
        conn
    )

    data = {}
    for year in years_df['year']:
        if exclude_year is not None and year == str(exclude_year):
            continue
        df = pd.read_sql_query(
            "SELECT date AS Date, passengers AS Passenger_Numbers "
            "FROM passenger_data WHERE strftime('%Y', date) = ? ORDER BY date",
            conn, params=(year,)
        )
        df['Date'] = pd.to_datetime(df['Date'])
        data[year] = df
        print(f"已加载 {year} 年数据: {len(df)} 条记录")

    conn.close()
    return data


def save_data(data, year):
    """
    将DataFrame数据保存（或更新）到SQLite数据库（upsert）

    参数:
    data: DataFrame，包含 Date 和 Passenger_Numbers 列
    year: 年份（仅用于日志输出）
    """
    db_path = get_db_path()
    init_db()

    conn = sqlite3.connect(db_path)

    rows = [
        (row['Date'].strftime('%Y-%m-%d'), int(row['Passenger_Numbers']))
        for _, row in data.iterrows()
    ]

    conn.executemany(
        "INSERT OR REPLACE INTO passenger_data (date, passengers) VALUES (?, ?)",
        rows
    )
    conn.commit()

    inserted = conn.execute(
        "SELECT COUNT(*) FROM passenger_data WHERE strftime('%Y', date) = ?",
        (str(year),)
    ).fetchone()[0]

    conn.close()
    print(f"{year} 年数据已保存到数据库（共 {inserted} 条记录）")


def migrate_pkl_to_sqlite():
    """
    将现有的pkl文件迁移到SQLite数据库（一次性操作，可重复运行）

    搜索项目根目录及 script 目录下所有 passenger_data_YYYY.pkl 文件并导入。
    """
    import pickle

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    init_db()

    search_dirs = [project_root, script_dir]
    pkl_files = []
    for d in search_dirs:
        pkl_files.extend(glob(os.path.join(d, 'passenger_data_*.pkl')))

    # 去重（同一文件可能被两个目录各找到一次）
    pkl_files = list(set(pkl_files))

    if not pkl_files:
        print("未找到需要迁移的pkl文件")
        return

    migrated = 0
    for pkl_path in sorted(pkl_files):
        filename = os.path.basename(pkl_path)
        try:
            year = filename.replace('passenger_data_', '').replace('.pkl', '')
            int(year)  # 验证是有效的年份数字
        except ValueError:
            print(f"跳过无法解析年份的文件: {filename}")
            continue

        try:
            with open(pkl_path, 'rb') as f:
                df = pickle.load(f)
            save_data(df, year)
            print(f"已迁移: {filename} ({len(df)} 条记录)")
            migrated += 1
        except Exception as e:
            print(f"迁移 {filename} 时出错: {e}")

    print(f"\n迁移完成，共处理 {migrated} 个pkl文件")


if __name__ == "__main__":
    try:
        latest_data = scrape_latest_data()
        print(f"成功获取最新数据: {len(latest_data)} 条记录")
        print(latest_data.head())
    except Exception as e:
        print(f"获取数据时出错: {e}")
