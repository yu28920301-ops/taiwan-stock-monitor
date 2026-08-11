import requests
import time
from datetime import datetime

# =========================================================
# 台股即時行情監控
# =========================================================

STOCKS = {
    "2330": "台積電",
    "0050": "元大台灣50",
    "00981A": "主動統一台股增長",
    "00891": "中信關鍵半導體",
    "2412": "中華電",
}

API_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

# 每幾秒更新一次
UPDATE_SECONDS = 10

# API 失敗最多重試幾次
MAX_RETRY = 3


# =========================================================
# 取得 TWSE 即時行情
# =========================================================

def get_market_data():

    # 加權指數
    query = ["tse_t00.tw"]

    # 5 檔股票 / ETF
    for code in STOCKS:
        query.append(f"tse_{code}.tw")

    params = {
        "ex_ch": "|".join(query),
        "json": "1",
        "delay": "0",
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://mis.twse.com.tw/",
    }

    for retry in range(1, MAX_RETRY + 1):

        try:

            response = requests.get(
                API_URL,
                params=params,
                headers=headers,
                timeout=15,
            )

            response.raise_for_status()

            result = response.json()

            data = result.get("msgArray", [])

            if data:
                return data

            print(
                f"⚠️ 第 {retry} 次取得不到行情，重新嘗試..."
            )

        except Exception as e:

            print(
                f"⚠️ 第 {retry} 次 API 錯誤：{e}"
            )

        if retry < MAX_RETRY:
            time.sleep(3)

    return []


# =========================================================
# 找股票
# =========================================================

def find_data(data, code):

    for item in data:

        if item.get("c") == code:
            return item

    return None


# =========================================================
# 計算漲跌
# =========================================================

def calculate_change(item):

    if not item:
        return None, None

    latest = item.get("z")
    previous = item.get("y")

    try:

        if latest in ("", "-", None):
            return None, None

        if previous in ("", "-", None):
            return None, None

        latest = float(latest)
        previous = float(previous)

        change = latest - previous

        if previous != 0:
            percent = change / previous * 100
        else:
            percent = 0

        return change, percent

    except Exception:

        return None, None


# =========================================================
# 顯示加權指數
# =========================================================

def show_index(data):

    item = find_data(data, "t00")

    print()
    print("📈【加權指數】")
    print("-" * 55)

    if not item:

        print("目前沒有取得加權指數")

        return

    latest = item.get("z", "-")

    change, percent = calculate_change(item)

    print(f"即時指數：{latest}")

    if change is not None:

        print(f"漲跌：{change:+.2f}")
        print(f"漲跌幅：{percent:+.2f}%")

    else:

        print("漲跌：-")
        print("漲跌幅：-")

    print(
        f"成交量：{item.get('v', '-')}"
    )

    print(
        f"成交時間：{item.get('t', '-')}"
    )


# =========================================================
# 顯示股票
# =========================================================

def show_stock(data, code, name):

    item = find_data(data, code)

    print()
    print(f"💰【{code}｜{name}】")
    print("-" * 55)

    if not item:

        print("目前沒有取得資料")

        return

    latest = item.get("z", "-")

    previous = item.get("y", "-")

    change, percent = calculate_change(item)

    print(
        f"即時價格：{latest}"
    )

    print(
        f"昨收：{previous}"
    )

    if change is not None:

        print(
            f"漲跌：{change:+.2f}"
        )

        print(
            f"漲跌幅：{percent:+.2f}%"
        )

    else:

        print("漲跌：-")
        print("漲跌幅：-")

    print(
        f"成交量：{item.get('v', '-')}"
    )

    print(
        f"成交時間：{item.get('t', '-')}"
    )


# =========================================================
# 顯示全部行情
# =========================================================

def show_market(data):

    now = datetime.now()

    print()
    print("=" * 60)
    print("🇹🇼 TAIWAN STOCK REAL-TIME MONITOR")
    print("=" * 60)

    print(
        f"日期：{now.strftime('%Y-%m-%d')}"
    )

    print(
        f"更新時間：{now.strftime('%H:%M:%S')}"
    )

    print("=" * 60)

    # 加權指數
    show_index(data)

    # 股票
    print()
    print("=" * 60)
    print("📊 即時股票 / ETF")
    print("=" * 60)

    for code, name in STOCKS.items():

        show_stock(
            data,
            code,
            name
        )

    print()
    print("=" * 60)


# =========================================================
# 主程式
# =========================================================

def main():

    print()
    print("🚀 台股即時行情監控啟動")
    print()
    print("監控項目：")
    print("📈 加權指數")
    
    for code, name in STOCKS.items():
        print(f"💰 {code} {name}")

    print()
    print(
        f"更新頻率：每 {UPDATE_SECONDS} 秒"
    )
    print()

    while True:

        data = get_market_data()

        if data:

            show_market(data)

        else:

            print()
            print("❌ 本輪沒有取得行情")
            print("🔄 下一輪重新嘗試")
            print()

        time.sleep(
            UPDATE_SECONDS
        )


# =========================================================
# 程式入口
# =========================================================

if __name__ == "__main__":
    main()
