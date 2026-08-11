import json
import os
import time
from datetime import datetime, timezone, timedelta

import requests


# ============================================================
# Taiwan Stock Monitor
# 台股即時行情 + 加權指數 + 三大法人 + 每日資料保存
# ============================================================

TW_TIMEZONE = timezone(timedelta(hours=8))

STOCKS = {
    "2330": "台積電",
    "0050": "元大台灣50",
    "00981A": "主動統一台股增長",
    "00891": "中信關鍵半導體",
    "2412": "中華電",
}

# TWSE MIS 即時行情 API
STOCK_API = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

# TWSE 加權指數即時行情 API
INDEX_API = "https://mis.twse.com.tw/stock/api/getIndexInfo.jsp"

# TWSE 三大法人買賣金額
INSTITUTION_API = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"

REQUEST_TIMEOUT = 15
MAX_RETRY = 3

DATA_DIR = "data"


# ============================================================
# 基本工具
# ============================================================

def now_tw():
    """取得目前台灣時間"""
    return datetime.now(TW_TIMEZONE)


def tw_date():
    """YYYYMMDD"""
    return now_tw().strftime("%Y%m%d")


def tw_date_display():
    """YYYY-MM-DD"""
    return now_tw().strftime("%Y-%m-%d")


def tw_time():
    """HH:MM:SS"""
    return now_tw().strftime("%H:%M:%S")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def safe_float(value):
    try:
        if value is None:
            return None

        text = str(value).strip()

        if text in ("", "-", "--", "None", "null"):
            return None

        return float(text.replace(",", ""))

    except Exception:
        return None


def safe_int(value):
    number = safe_float(value)

    if number is None:
        return None

    return int(number)


def format_number(value, digits=2):
    if value is None:
        return "-"

    return f"{value:,.{digits}f}"


def format_integer(value):
    if value is None:
        return "-"

    return f"{int(value):,}"


# ============================================================
# HTTP
# ============================================================

def http_get_json(url, params=None):
    """
    穩定取得 JSON。
    失敗會重試。
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Safari/604.1"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://mis.twse.com.tw/",
    }

    last_error = None

    for attempt in range(1, MAX_RETRY + 1):

        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            return response.json()

        except Exception as exc:
            last_error = exc

            print(
                f"⚠️ API 第 {attempt}/{MAX_RETRY} 次失敗："
                f"{type(exc).__name__}: {exc}"
            )

            if attempt < MAX_RETRY:
                time.sleep(2)

    raise RuntimeError(
        f"API 取得失敗，已重試 {MAX_RETRY} 次：{last_error}"
    )


# ============================================================
# 即時個股
# ============================================================

def get_stock_data():

    exchange_codes = []

    for code in STOCKS:

        # 上市股票
        exchange_codes.append(f"tse_{code}.tw")

    params = {
        "ex_ch": "|".join(exchange_codes),
        "json": "1",
        "delay": "0",
        "_": int(time.time() * 1000),
    }

    data = http_get_json(STOCK_API, params)

    msg_array = data.get("msgArray", [])

    result = {}

    for item in msg_array:

        code = item.get("c")

        if code not in STOCKS:
            continue

        name = STOCKS[code]

        # z = 最新成交價
        price = safe_float(item.get("z"))

        # y = 昨日收盤
        previous_close = safe_float(item.get("y"))

        # o = 開盤
        open_price = safe_float(item.get("o"))

        # h = 最高
        high_price = safe_float(item.get("h"))

        # l = 最低
        low_price = safe_float(item.get("l"))

        # v = 成交量
        volume = safe_int(item.get("v"))

        # t = 最新成交時間
        trade_time = item.get("t")

        # tv = 最新一筆成交量
        trade_volume = safe_int(item.get("tv"))

        # 如果 z 無資料，避免把缺資料當作正常價格
        if price is None:
            price = previous_close

        change = None
        change_percent = None

        if price is not None and previous_close not in (None, 0):
            change = price - previous_close
            change_percent = change / previous_close * 100

        result[code] = {
            "code": code,
            "name": name,
            "price": price,
            "previous_close": previous_close,
            "change": change,
            "change_percent": change_percent,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "volume": volume,
            "trade_volume": trade_volume,
            "trade_time": trade_time,
            "source": "TWSE MIS",
        }

    # 確保所有股票都有結果
    for code, name in STOCKS.items():

        if code not in result:

            result[code] = {
                "code": code,
                "name": name,
                "price": None,
                "previous_close": None,
                "change": None,
                "change_percent": None,
                "open": None,
                "high": None,
                "low": None,
                "volume": None,
                "trade_volume": None,
                "trade_time": None,
                "source": "TWSE MIS",
                "error": "未取得行情",
            }

    return result


# ============================================================
# 加權指數
# ============================================================

def get_taiex():

    params = {
        "ex_ch": "tse_t00.tw",
        "json": "1",
        "delay": "0",
        "_": int(time.time() * 1000),
    }

    data = http_get_json(INDEX_API, params)

    msg_array = data.get("msgArray", [])

    if not msg_array:
        raise RuntimeError("TWSE 未回傳加權指數資料")

    item = msg_array[0]

    # 常見欄位：
    # z = 最新指數
    # y = 昨收
    # o = 開盤
    # h = 最高
    # l = 最低
    # t = 時間

    index_value = safe_float(item.get("z"))

    if index_value is None:
        index_value = safe_float(item.get("i"))

    previous_close = safe_float(item.get("y"))

    open_value = safe_float(item.get("o"))
    high_value = safe_float(item.get("h"))
    low_value = safe_float(item.get("l"))

    change = None
    change_percent = None

    if (
        index_value is not None
        and previous_close not in (None, 0)
    ):
        change = index_value - previous_close
        change_percent = change / previous_close * 100

    return {
        "name": "加權指數",
        "code": "TAIEX",
        "value": index_value,
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_percent,
        "open": open_value,
        "high": high_value,
        "low": low_value,
        "time": item.get("t"),
        "source": "TWSE MIS",
    }


# ============================================================
# 三大法人
# ============================================================

def get_institutional_data():

    date_string = tw_date()

    params = {
        "date": date_string,
        "selectType": "ALLBUT0999",
        "response": "json",
    }

    data = http_get_json(INSTITUTION_API, params)

    rows = data.get("data", [])

    result = {
        "date": date_string,
        "foreign": None,
        "investment_trust": None,
        "dealer": None,
        "total": None,
        "source": "TWSE BFI82U",
    }

    for row in rows:

        if not row:
            continue

        category = str(row[0]).strip()

        # BFI82U：
        # 類別 / 買進金額 / 賣出金額 / 買賣超

        if len(row) < 4:
            continue

        buy = safe_float(row[1])
        sell = safe_float(row[2])
        net = safe_float(row[3])

        item = {
            "buy": buy,
            "sell": sell,
            "net": net,
        }

        if "外資" in category:
            result["foreign"] = item

        elif "投信" in category:
            result["investment_trust"] = item

        elif "自營商" in category:
            result["dealer"] = item

        elif "合計" in category:
            result["total"] = item

    return result


# ============================================================
# 單位轉換
# ============================================================

def yuan_to_billion(value):
    """
    TWSE BFI82U 金額轉為億元。
    """

    if value is None:
        return None

    return value / 100_000_000


def convert_institution_units(data):

    converted = {
        "date": data.get("date"),
        "foreign": None,
        "investment_trust": None,
        "dealer": None,
        "total": None,
        "source": data.get("source"),
    }

    for key in (
        "foreign",
        "investment_trust",
        "dealer",
        "total",
    ):

        item = data.get(key)

        if item is None:
            continue

        converted[key] = {
            "buy_billion": yuan_to_billion(item.get("buy")),
            "sell_billion": yuan_to_billion(item.get("sell")),
            "net_billion": yuan_to_billion(item.get("net")),
        }

    return converted


# ============================================================
# 顯示即時資料
# ============================================================

def print_realtime(index_data, stocks):

    print()
    print("=" * 70)
    print("📈 台股即時行情")
    print("=" * 70)

    print(f"日期：{tw_date_display()}")
    print(f"台灣時間：{tw_time()}")

    print()

    # 加權指數
    print("【加權指數】")

    if index_data.get("value") is None:

        print("⚠️ 加權指數：取得失敗")

    else:

        print(
            f"加權指數："
            f"{format_number(index_data['value'], 2)}"
        )

        print(
            f"漲跌："
            f"{format_number(index_data['change'], 2)}"
        )

        print(
            f"漲跌幅："
            f"{format_number(index_data['change_percent'], 2)}%"
        )

        print(
            f"成交時間："
            f"{index_data.get('time') or '-'}"
        )

    print()

    print("【個股／ETF】")

    for code in STOCKS:

        item = stocks.get(code, {})

        print("-" * 70)

        print(
            f"{code}  {item.get('name', STOCKS[code])}"
        )

        if item.get("price") is None:

            print("⚠️ 最新價格：取得失敗")

        else:

            print(
                f"最新價格："
                f"{format_number(item.get('price'), 4)}"
            )

            print(
                f"漲跌："
                f"{format_number(item.get('change'), 4)}"
            )

            print(
                f"漲跌幅："
                f"{format_number(item.get('change_percent'), 2)}%"
            )

            print(
                f"成交量："
                f"{format_integer(item.get('volume'))}"
            )

            print(
                f"成交時間："
                f"{item.get('trade_time') or '-'}"
            )

    print()
    print("=" * 70)


# ============================================================
# 顯示三大法人
# ============================================================

def print_institutional(data):

    print()
    print("=" * 70)
    print("🏦 三大法人買賣金額")
    print("=" * 70)

    print(f"資料日期：{data.get('date')}")

    names = {
        "foreign": "外資",
        "investment_trust": "投信",
        "dealer": "自營商",
        "total": "三大法人合計",
    }

    for key, name in names.items():

        item = data.get(key)

        if item is None:
            print(f"{name}：資料尚未取得")
            continue

        print("-" * 70)

        print(
            f"{name}"
            f"｜買進：{format_number(item.get('buy_billion'), 2)} 億"
            f"｜賣出：{format_number(item.get('sell_billion'), 2)} 億"
            f"｜買賣超：{format_number(item.get('net_billion'), 2)} 億"
        )

    print("=" * 70)


# ============================================================
# 建立完整 Snapshot
# ============================================================

def create_snapshot():

    current_time = now_tw()

    snapshot = {
        "date": current_time.strftime("%Y-%m-%d"),
        "date_compact": current_time.strftime("%Y%m%d"),
        "taiwan_time": current_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "timezone": "UTC+8",
        "index": None,
        "stocks": {},
        "institutional": None,
    }

    # --------------------------------------------------------
    # 加權指數
    # --------------------------------------------------------

    try:

        snapshot["index"] = get_taiex()

    except Exception as exc:

        snapshot["index"] = {
            "code": "TAIEX",
            "name": "加權指數",
            "value": None,
            "error": str(exc),
            "source": "TWSE MIS",
        }

        print(f"⚠️ 加權指數取得失敗：{exc}")

    # --------------------------------------------------------
    # 個股
    # --------------------------------------------------------

    try:

        snapshot["stocks"] = get_stock_data()

    except Exception as exc:

        print(f"⚠️ 個股行情取得失敗：{exc}")

        for code, name in STOCKS.items():

            snapshot["stocks"][code] = {
                "code": code,
                "name": name,
                "price": None,
                "change": None,
                "change_percent": None,
                "volume": None,
                "trade_time": None,
                "error": str(exc),
                "source": "TWSE MIS",
            }

    # --------------------------------------------------------
    # 三大法人
    # --------------------------------------------------------

    try:

        institutional = get_institutional_data()

        snapshot["institutional"] = (
            convert_institution_units(institutional)
        )

    except Exception as exc:

        print(f"⚠️ 三大法人取得失敗：{exc}")

        snapshot["institutional"] = {
            "date": tw_date(),
            "foreign": None,
            "investment_trust": None,
            "dealer": None,
            "total": None,
            "error": str(exc),
            "source": "TWSE BFI82U",
        }

    return snapshot


# ============================================================
# 儲存資料
# ============================================================

def save_snapshot(snapshot):

    ensure_data_dir()

    date_string = snapshot["date"]

    daily_file = os.path.join(
        DATA_DIR,
        f"{date_string}.json",
    )

    latest_file = os.path.join(
        DATA_DIR,
        "latest.json",
    )

    # 每日資料
    with open(
        daily_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            snapshot,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # 最新資料
    with open(
        latest_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            snapshot,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("💾 資料已保存")
    print(f"每日資料：{daily_file}")
    print(f"最新資料：{latest_file}")


# ============================================================
# 每日收盤彙整
# ============================================================

def create_daily_summary(snapshot):

    ensure_data_dir()

    date_string = snapshot["date"]

    summary_file = os.path.join(
        DATA_DIR,
        f"{date_string}_summary.json",
    )

    summary = {
        "date": snapshot["date"],
        "taiwan_time": snapshot["taiwan_time"],
        "index": snapshot.get("index"),
        "stocks": {},
        "institutional": snapshot.get(
            "institutional"
        ),
    }

    for code, item in snapshot.get(
        "stocks",
        {}
    ).items():

        summary["stocks"][code] = {
            "code": code,
            "name": item.get("name"),
            "price": item.get("price"),
            "previous_close": item.get(
                "previous_close"
            ),
            "change": item.get("change"),
            "change_percent": item.get(
                "change_percent"
            ),
            "volume": item.get("volume"),
            "trade_time": item.get(
                "trade_time"
            ),
        }

    with open(
        summary_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("📊 每日收盤彙整檔已建立：")
    print(summary_file)


# ============================================================
# 顯示每日彙整
# ============================================================

def print_daily_summary(snapshot):

    print()
    print()
    print("#" * 70)
    print("📊 今日台股資料彙整")
    print("#" * 70)

    print(
        f"日期：{snapshot.get('date')}"
    )

    print(
        f"最後更新：{snapshot.get('taiwan_time')}"
    )

    print()

    # --------------------------------------------------------
    # 指數
    # --------------------------------------------------------

    index_data = snapshot.get("index") or {}

    print("【加權指數】")

    if index_data.get("value") is not None:

        print(
            f"指數："
            f"{format_number(index_data.get('value'), 2)}"
        )

        print(
            f"漲跌："
            f"{format_number(index_data.get('change'), 2)}"
        )

        print(
            f"漲跌幅："
            f"{format_number(index_data.get('change_percent'), 2)}%"
        )

    else:

        print("⚠️ 指數資料不足")

    print()

    # --------------------------------------------------------
    # 股票
    # --------------------------------------------------------

    print("【個股／ETF】")

    for code in STOCKS:

        item = snapshot["stocks"].get(
            code,
            {},
        )

        print(
            f"{code} "
            f"{item.get('name', STOCKS[code])}"
        )

        print(
            f"  價格："
            f"{format_number(item.get('price'), 4)}"
        )

        print(
            f"  漲跌："
            f"{format_number(item.get('change'), 4)}"
        )

        print(
            f"  漲跌幅："
            f"{format_number(item.get('change_percent'), 2)}%"
        )

        print(
            f"  成交量："
            f"{format_integer(item.get('volume'))}"
        )

    print()

    # --------------------------------------------------------
    # 三大法人
    # --------------------------------------------------------

    print("【三大法人】")

    institutional = snapshot.get(
        "institutional"
    ) or {}

    labels = {
        "foreign": "外資",
        "investment_trust": "投信",
        "dealer": "自營商",
        "total": "合計",
    }

    for key, label in labels.items():

        item = institutional.get(key)

        if not item:
            print(
                f"{label}：資料不足"
            )
            continue

        print(
            f"{label}"
            f"｜買進 "
            f"{format_number(item.get('buy_billion'), 2)} 億"
            f"｜賣出 "
            f"{format_number(item.get('sell_billion'), 2)} 億"
            f"｜買賣超 "
            f"{format_number(item.get('net_billion'), 2)} 億"
        )

    print()

    print("#" * 70)


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 70)
    print("🇹🇼 Taiwan Stock Monitor")
    print("=" * 70)

    print(
        f"開始時間：{now_tw().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        "資料來源：TWSE"
    )

    print()

    # 取得完整資料
    snapshot = create_snapshot()

    # 顯示即時行情
    print_realtime(
        snapshot.get("index") or {},
        snapshot.get("stocks") or {},
    )

    # 三大法人
    print_institutional(
        snapshot.get("institutional") or {}
    )

    # 每次執行保存資料
    save_snapshot(snapshot)

    # 建立每日彙整
    create_daily_summary(snapshot)

    # 最終輸出
    print_daily_summary(snapshot)

    print()
    print(
        f"完成時間：{now_tw().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print("=" * 70)
    print("✅ Taiwan Stock Monitor 執行完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
