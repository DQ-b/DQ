import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = Path(os.environ.get("CHENGHAI_INPUT_DIR", SCRIPT_DIR)).resolve()
OUTPUT_DIR = Path(os.environ.get("CHENGHAI_OUTPUT_DIR", SCRIPT_DIR / "outputs" / "chenghai_toy_top")).resolve()
WORKBOOK_BUILDER = SCRIPT_DIR / "chenghai_toy_top_workbooks.mjs"
NODE_EXE = Path(r"C:\Users\HI\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")
NODE_MODULES_SOURCE = Path(r"C:\Users\HI\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules")

INPUT_FILES = {
    "taobao": "taobao.csv",
    "pdd": "pdd.csv",
    "douyin": "douyin.csv",
    "1688": "1688.csv",
}

STANDARD_COLUMNS = [
    "platform",
    "title",
    "shop_name",
    "sales_display",
    "sales_num",
    "price",
    "location",
    "product_url",
    "is_chenghai",
    "data_note",
]

FIELD_ALIASES = {
    "title": [
        "商品标题",
        "标题",
        "商品名称",
        "产品标题",
        "宝贝标题",
        "name",
        "title",
    ],
    "shop_name": [
        "店铺名",
        "店铺名称",
        "商家名",
        "商家名称",
        "供应商",
        "店铺",
        "shop",
        "seller",
    ],
    "sales_display": [
        "销量",
        "销量区间",
        "已售",
        "成交量",
        "付款人数",
        "销售量",
        "sales",
        "sold",
    ],
    "price": [
        "价格",
        "商品价格",
        "售价",
        "单价",
        "price",
    ],
    "location": [
        "发货地",
        "商家地址",
        "地址",
        "产地",
        "所在地",
        "地区",
        "location",
        "address",
    ],
    "product_url": [
        "商品链接",
        "链接",
        "商品URL",
        "商品网址",
        "url",
        "link",
    ],
    "platform": [
        "平台名",
        "平台",
        "来源平台",
        "platform",
    ],
}


def normalize_header(value):
    return re.sub(r"\s+", "", str(value or "")).lower()


NORMALIZED_ALIASES = {
    target: {normalize_header(alias) for alias in aliases}
    for target, aliases in FIELD_ALIASES.items()
}


def decode_csv(path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def read_csv_rows(path):
    text, encoding = decode_csv(path)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    rows = list(reader)
    return rows, encoding, reader.fieldnames or []


def build_field_map(fieldnames):
    normalized_to_original = {
        normalize_header(name): name
        for name in fieldnames
        if name is not None
    }
    mapped = {}
    for target, aliases in NORMALIZED_ALIASES.items():
        for alias in aliases:
            if alias in normalized_to_original:
                mapped[target] = normalized_to_original[alias]
                break
    return mapped


def get_value(row, field_map, target):
    source_key = field_map.get(target)
    if not source_key:
        return ""
    value = row.get(source_key, "")
    if value is None:
        return ""
    return str(value).strip()


def normalize_platform(raw_platform, fallback):
    platform = (raw_platform or fallback).strip()
    names = {
        "taobao": "淘宝",
        "pdd": "拼多多",
        "douyin": "抖音",
        "1688": "1688",
    }
    return names.get(platform.lower(), platform)


def parse_sales_num(value):
    text = str(value or "").strip()
    if not text:
        return 0

    text = text.replace(",", "").replace("，", "")
    text = re.sub(r"\s+", "", text)
    text = text.replace("＋", "+")

    range_match = re.search(
        r"(\d+(?:\.\d+)?)(万|w|W|千|k|K)?(?:[-~至到—]+)(\d+(?:\.\d+)?)(万|w|W|千|k|K)?",
        text,
    )
    if range_match:
        number = float(range_match.group(1))
        unit = range_match.group(2) or range_match.group(4) or ""
        return int(number * unit_multiplier(unit))

    number_match = re.search(r"(\d+(?:\.\d+)?)(万|w|W|千|k|K)?", text)
    if not number_match:
        return 0

    number = float(number_match.group(1))
    unit = number_match.group(2) or ""
    return int(number * unit_multiplier(unit))


def unit_multiplier(unit):
    if unit in ("万", "w", "W"):
        return 10000
    if unit in ("千", "k", "K"):
        return 1000
    return 1


def is_chenghai_location(location):
    return bool(re.search(r"澄海|汕头", str(location or "")))


def ensure_node_modules_link():
    target = SCRIPT_DIR / "node_modules"
    if target.exists():
        return
    if not NODE_MODULES_SOURCE.exists():
        raise FileNotFoundError(f"找不到表格依赖目录: {NODE_MODULES_SOURCE}")
    try:
        target.symlink_to(NODE_MODULES_SOURCE, target_is_directory=True)
    except OSError:
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(NODE_MODULES_SOURCE)],
            cwd=SCRIPT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )


def load_all_inputs():
    missing = []
    all_rows = []
    sources = []

    for platform_key, filename in INPUT_FILES.items():
        path = INPUT_DIR / filename
        if not path.exists():
            missing.append(filename)
            continue

        rows, encoding, fieldnames = read_csv_rows(path)
        field_map = build_field_map(fieldnames)
        sources.append(
            {
                "file": filename,
                "platform_key": platform_key,
                "encoding": encoding,
                "rows": len(rows),
                "mapped_fields": field_map,
            }
        )

        for row in rows:
            platform = normalize_platform(get_value(row, field_map, "platform"), platform_key)
            sales_display = get_value(row, field_map, "sales_display")
            location = get_value(row, field_map, "location")
            is_chenghai = is_chenghai_location(location)
            all_rows.append(
                {
                    "platform": platform,
                    "title": get_value(row, field_map, "title"),
                    "shop_name": get_value(row, field_map, "shop_name"),
                    "sales_display": sales_display,
                    "sales_num": parse_sales_num(sales_display),
                    "price": get_value(row, field_map, "price"),
                    "location": location,
                    "product_url": get_value(row, field_map, "product_url"),
                    "is_chenghai": "是" if is_chenghai else "否",
                    "data_note": "销量为平台展示值,非真实成交",
                }
            )

    if missing:
        raise FileNotFoundError("缺少输入文件: " + ", ".join(missing))

    return all_rows, sources


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=STANDARD_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def make_rankings(rows):
    chenghai_rows = [row for row in rows if row["is_chenghai"] == "是"]
    chenghai_rows.sort(key=lambda row: row["sales_num"], reverse=True)

    platform_top = {}
    for row in chenghai_rows:
        platform_top.setdefault(row["platform"], []).append(row)
    platform_top = {
        platform: platform_rows[:10]
        for platform, platform_rows in sorted(platform_top.items())
    }

    overall_top20 = chenghai_rows[:20]
    return chenghai_rows, platform_top, overall_top20


def make_summary(overall_top20):
    if not overall_top20:
        return "当前输入数据中未找到发货地/商家地址含“澄海”或“汕头”的记录，无法生成销量第一单品总结。"

    top = overall_top20[0]
    title = top["title"] or "未填写商品标题"
    platform = top["platform"] or "未知平台"
    shop = top["shop_name"] or "未填写店铺名"
    sales_display = top["sales_display"] or "未填写销量展示值"
    sales_num = top["sales_num"]
    price = top["price"] or "未填写价格"
    location = top["location"] or "未填写发货地/商家地址"

    return (
        f"当前澄海/汕头筛选记录中，销量下限排名第一的单品为“{title}”，"
        f"来自{platform}平台，店铺为“{shop}”。平台展示销量为“{sales_display}”，"
        f"折算的可比销量下限为{sales_num}，价格为{price}，发货地/商家地址为“{location}”。"
        "需注意：销量为平台展示值,非真实成交。"
    )


def run_workbook_builder(payload_path):
    ensure_node_modules_link()
    if not NODE_EXE.exists():
        raise FileNotFoundError(f"找不到 Node.js 运行环境: {NODE_EXE}")
    subprocess.run(
        [str(NODE_EXE), str(WORKBOOK_BUILDER), str(payload_path)],
        cwd=SCRIPT_DIR,
        check=True,
    )


def main():
    try:
        all_rows, sources = load_all_inputs()
    except FileNotFoundError as exc:
        print(str(exc))
        print(f"请把 taobao.csv / pdd.csv / douyin.csv / 1688.csv 放在: {INPUT_DIR}")
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows.sort(key=lambda row: (row["platform"], -row["sales_num"], row["title"]))
    chenghai_rows, platform_top, overall_top20 = make_rankings(all_rows)

    cleaned_csv = OUTPUT_DIR / "cleaned_all.csv"
    payload_json = OUTPUT_DIR / "chenghai_rankings_payload.json"
    summary_txt = OUTPUT_DIR / "top_item_summary.txt"

    write_csv(cleaned_csv, all_rows)
    payload = {
        "columns": STANDARD_COLUMNS,
        "all_rows": all_rows,
        "chenghai_rows": chenghai_rows,
        "platform_top": platform_top,
        "overall_top20": overall_top20,
        "sources": sources,
        "outputs": {
            "top_by_platform": str(OUTPUT_DIR / "chenghai_top_by_platform.xlsx"),
            "overall_top20": str(OUTPUT_DIR / "chenghai_overall_top20.xlsx"),
        },
    }
    payload_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_txt.write_text(make_summary(overall_top20), encoding="utf-8")
    run_workbook_builder(payload_json)

    print(f"已生成: {cleaned_csv}")
    print(f"已生成: {OUTPUT_DIR / 'chenghai_top_by_platform.xlsx'}")
    print(f"已生成: {OUTPUT_DIR / 'chenghai_overall_top20.xlsx'}")
    print(f"第一名单品总结: {summary_txt.read_text(encoding='utf-8')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
