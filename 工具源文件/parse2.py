import re, json, io

# ---------- 本科目录（已经用 extract_tables 解析好） ----------
import pdfplumber
BK_DISC = {'01':'哲学','02':'经济学','03':'法学','04':'教育学','05':'文学','06':'历史学','07':'理学','08':'工学','09':'农学','10':'医学','12':'管理学','13':'艺术学'}
bk = []
with pdfplumber.open('_moe2024.pdf') as pdf:
    for p in pdf.pages:
        for tb in p.extract_tables():
            for row in tb:
                if not row: continue
                cells=[(c or '').replace('\n',' ').strip() for c in row]
                ci=None
                for i,c in enumerate(cells):
                    if re.match(r'^[0-9]{6}[TK]{0,2}$', c): ci=i; break
                if ci is None or ci==0: continue
                code=cells[ci]; name=cells[ci+1] if ci+1<len(cells) else ''
                cat=''
                for j in range(ci-1,-1,-1):
                    if cells[j].endswith('类'): cat=cells[j]; break
                if not name or not cat: continue
                bk.append({'code':code,'name':name.strip(),'cat':cat,'disc':BK_DISC.get(code[:2],''),'level':'本科'})
seen={r['code']:r for r in bk}; bk=list(seen.values())
print('本科专业:', len(bk))

# ---------- 研究生目录 ----------
raw = io.open('_grad_raw.txt', encoding='utf-8').read()
lines = [l.strip() for l in raw.split('\n') if l.strip()]
GD_DISC = {}   # 门类代码 -> 名称
grad = []
cur_disc_code, cur_disc_name = None, None
# 门类行： "01 哲学"
DISC_RE = re.compile(r'^(\d{2})\s+([\u4e00-\u9fa5]{2,6})$')
# 学科行： "0101 哲学" 或 "0151 应用伦理 *"
ITEM_RE = re.compile(r'^(\d{4})\s+(.+)$')

for ln in lines:
    m = DISC_RE.match(ln)
    if m and not re.match(r'^\d{4}', ln):
        cur_disc_code, cur_disc_name = m.group(1), m.group(2)
        GD_DISC[cur_disc_code] = cur_disc_name
        continue
    m = ITEM_RE.match(ln)
    if m:
        code, rest = m.group(1), m.group(2)
        if not cur_disc_name: continue
        # 去掉括号备注和星号
        name = re.sub(r'[（(][^）)]*[）)]', '', rest).replace('*','').strip()
        if not name: continue
        is_pro = code[2] == '5'      # 第三位为 5 = 专业学位类别
        grad.append({'code':code,'name':name,'disc':cur_disc_name.decode() if isinstance(cur_disc_name,bytes) else cur_disc_name,
                     'cat':'', 'level':'研究生','isPro':is_pro})
print('研究生学科:', len(grad))
from collections import Counter
print('门类:', dict(Counter(r['disc'] for r in grad)))

# 合并：本科一级学科(4位前缀) + 研究生
# 建立"专业名称 -> 记录"的复合查找表
combined = {'benke': bk, 'yanjiu': grad}
io.open('_major_db.json','w',encoding='utf-8').write(json.dumps(combined, ensure_ascii=False, indent=1))

print()
print('本科 专业类清单:')
for c in sorted(set(r['cat'] for r in bk)): print(' ', c, end='')
print()
print()
print('研究生 门类清单:', list(GD_DISC.values()))
print()
for r in grad[:10]: print(r)
