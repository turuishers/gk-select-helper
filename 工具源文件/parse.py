import pdfplumber, json, io, re

DISC_NAMES = ['哲学','经济学','法学','教育学','文学','历史学','理学','工学','农学','医学','管理学','艺术学']
all_rows = []

with pdfplumber.open('_moe2024.pdf') as pdf:
    for p in pdf.pages:
        for tb in p.extract_tables():
            for row in tb:
                if not row:
                    continue
                cells = [(c or '').replace('\n', ' ').strip() for c in row]
                # 找含 6 位专业代码的单元格
                code_i = None
                for i, c in enumerate(cells):
                    if re.match(r'^[0-9]{6}[TK]{0,2}$', c):
                        code_i = i
                        break
                if code_i is None or code_i == 0:
                    continue
                code = cells[code_i]
                # 专业类在代码前一列（可能前一列是序号）
                cat = ''
                for j in range(code_i - 1, -1, -1):
                    if cells[j].endswith('类'):
                        cat = cells[j]
                        break
                # 专业名在代码后一列
                name = cells[code_i + 1] if code_i + 1 < len(cells) else ''
                name = name.strip()
                if not name or not cat:
                    continue
                all_rows.append({'code': code, 'name': name, 'cat': cat})

print('原始提取:', len(all_rows))

# 去重
seen = {}
for r in all_rows:
    seen[r['code']] = r
recs = list(seen.values())
recs.sort(key=lambda x: x['code'])
print('去重后:', len(recs))

# 补门类
def disc_of(cat):
    for d in DISC_NAMES:
        if cat.startswith(d): return d
    return ''
# 用代码前缀定门类更可靠
PREFIX_DISC = {'01':'哲学','02':'经济学','03':'法学','04':'教育学','05':'文学','06':'历史学','07':'理学','08':'工学','09':'农学','10':'医学','12':'管理学','13':'艺术学'}
for r in recs:
    r['disc'] = PREFIX_DISC.get(r['code'][:2], disc_of(r['cat']))

from collections import Counter
print('门类分布:', dict(Counter(r['disc'] for r in recs)))
print('专业类数:', len(set(r['cat'] for r in recs)))
print()
print('管理学样例:')
for r in recs:
    if r['disc']=='管理学': print(' ', r)
