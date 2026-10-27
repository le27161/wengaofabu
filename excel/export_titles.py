# -*- coding: utf-8 -*-
"""从 excel 目录下所有 *_raw.json 中抽取标题，按分类数字映射输出为「标题\t数字」文本。

分类数字映射：
    0 finance      1 realty       2 stocks      3 education   4 science
    5 society      6 politics     7 sports      8 game        9 entertainment

输出文件：与脚本同目录下的 1111.txt，一行一条「标题 数字」。
"""
import json
from pathlib import Path

EXCEL_DIR = Path(__file__).resolve().parent
OUTPUT = EXCEL_DIR / "1111.txt"

# 文件名前缀 -> 分类数字
FILE_TO_NUM = {
    "finance": 0,
    "house": 1,
    "stock": 2,
    "edu": 3,
    "science": 4,
    "society": 5,
    "politics": 6,
    "sports": 7,
    "game": 8,
    "entertainment": 9,
}

lines = []
missing = []
for raw_file in sorted(EXCEL_DIR.glob("*_raw.json")):
    prefix = raw_file.name[: -len("_raw.json")]
    num = FILE_TO_NUM.get(prefix)
    if num is None:
        missing.append(raw_file.name)
        continue
    with open(raw_file, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", data) if isinstance(data, dict) else data
    for item in items:
        title = (item.get("title") or "").strip()
        if title:
            lines.append(f"{title}\t{num}")

OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"已写入 {OUTPUT}，共 {len(lines)} 行")
if missing:
    print("未匹配到映射的文件（已跳过）:", missing)
