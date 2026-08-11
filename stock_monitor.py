import requests
import time
from datetime import datetime

# 目前關注的股票
STOCKS = {
    "2330": "台積電",
    "0050": "元大台灣50",
    "00981A": "00981A",
    "00891": "中信小資高價30",
    "2412": "中華電",
}

URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"


def get_stock_price(stock_id, name):
    params = {
        "ex_ch": f"tse_{stock_id}.tw",
        "json": "1",
        "delay": "0",
        "time": datetime.now().strftime("%Y%m%d%H%M%S"),
    }

    try:
        response = requests.get(
            URL,
            params=params,
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

        if not data.get("msgArray"):
            return {
                "代號": stock_id,
                "名稱": name,
                "狀態": "無資料"
            }

        stock = data["msgArray"][0]

        return {
            "代號": stock.get("c", stock_id),
            "名稱": stock.get("n", name),
            "最新價": stock.get("z", "-"),
            "漲跌": stock.get("d", "-"),
            "漲跌幅": stock.get("p", "-"),
            "成交量": stock.get("v", "-"),
            "時間": stock.get("t", "-"),
        }

    except Exception as e:
        return {
            "代號": stock_id,
            "名稱": name,
            "狀態": f"錯誤：{e}"
        }


def main():
    print("台股即時行情監控啟動")
    print("每 5 秒更新一次")
    print("按 Ctrl+C 可停止")
    print("=" * 80)

    while True:

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print()
        print("=" * 80)
        print(f"更新時間：{now}")
        print("=" * 80)

        for stock_id, name in STOCKS.items():

            result = get_stock_price(stock_id, name)

            print(
                f"{result.get('代號', stock_id):<8}"
                f"{result.get('名稱', name):<12}"
                f"最新：{result.get('最新價', '-'):<10}"
                f"漲跌：{result.get('漲跌', '-'):<8}"
                f"漲幅：{result.get('漲跌幅', '-'):<8}"
                f"量：{result.get('成交量', '-'):<10}"
                f"時間：{result.get('時間', '-')}"
            )

        time.sleep(5)


if __name__ == "__main__":
    main()
