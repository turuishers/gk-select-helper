# -*- coding: utf-8 -*-
"""
第 1 步：解析当年国考职位表 Excel -> raw JSON

用法：改下面 CONFIG 区，然后
    python 1-解析原始表.py

产出 raw<年份>.json：27 个中文字段 + _sheet，字段名与 HTML 里 norm() 的取值一致。
"""
from pathlib import Path
import json
import xlrd

# ==================== CONFIG（每年只改这里） ====================
YEAR = 2027
# 当年国考招考简章（官方 .xls）。换成你本机上的实际路径，例如：
#   XLS = Path(r"D:\国考\中央机关及其直属机构2027年度考试录用公务员招考简章.xls")
XLS = Path(r"<填入本机上当年招考简章 .xls 的完整路径>")
# ===============================================================

HERE = Path(__file__).resolve().parent
OUT = HERE / f"raw{YEAR}.json"

# 4 个正式 sheet（源表里可能还有空 sheet，不用列进来）
SHEETS = [
    '中央党群机关',
    '中央国家行政机关（本级）',
    '中央国家行政机关省级以下直属机构',
    '中央国家行政机关参照公务员法管理事业单位',
]
HEADER_ROW = 1          # 表头在第 2 行（0-based index=1）
SKIP_IF_EMPTY = '部门代码'   # 该列为空 = 尾部空行/小计行，丢弃


def main():
    wb = xlrd.open_workbook(str(XLS), on_demand=True)
    have = set(wb.sheet_names())
    missing = [s for s in SHEETS if s not in have]
    if missing:
        raise SystemExit(f"源表缺少 sheet：{missing}\n实际有：{wb.sheet_names()}")

    rows, header, per_sheet = [], None, {}
    for sn in SHEETS:
        sh = wb.sheet_by_name(sn)
        h = [str(sh.cell_value(HEADER_ROW, c)).strip() for c in range(sh.ncols)]
        if header is None:
            header = h
        elif h != header:
            raise SystemExit(f"!! sheet 表头不一致：{sn}\n{h}\nvs\n{header}")

        n0 = len(rows)
        for r in range(HEADER_ROW + 1, sh.nrows):
            rec = {}
            for c in range(sh.ncols):
                v = sh.cell_value(r, c)
                if isinstance(v, float) and v == int(v):
                    v = int(v)          # 1.0 -> 1，避免 "1.0" 污染正则
                rec[h[c]] = v
            if str(rec.get(SKIP_IF_EMPTY, '')).strip() in ('', 'None'):
                continue
            rec['_sheet'] = sn
            rows.append(rec)
        per_sheet[sn] = len(rows) - n0

    print("每 sheet 条数:", per_sheet)
    print("合计:", len(rows))
    OUT.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    print("->", OUT)
    print()
    print("下一步：跑 2-生成内嵌数据.js")
    print("（它会拿上一年的 html 算同比，所以上一年那个文件要还在）")


if __name__ == '__main__':
    main()
