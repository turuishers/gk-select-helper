import json, re, collections, io

db = json.load(io.open('_major_db.json', encoding='utf-8'))
bk, grad = db['benke'], db['yanjiu']

# 建立名称索引
name2cat = {}      # 专业名 -> (类, 门类, 层次)
for r in bk: name2cat[r['name']] = (r['cat'], r['disc'], '本科', r['code'])
for r in grad: 
    if r['name'] not in name2cat:
        name2cat[r['name']] = (r.get('cat',''), r['disc'], '研究生', r['code'])

cat2disc = {}
for r in bk: cat2disc[r['cat']] = r['disc']

io.open('_idx.json','w',encoding='utf-8').write(json.dumps({
  'name2cat':{k:list(v) for k,v in name2cat.items()},
  'cat2disc':cat2disc
}, ensure_ascii=False, indent=1))

# 读 2026 岗位表专业字段
import pandas as pd
xl = pd.ExcelFile(r'<填入本机上 2026国考.xls 的完整路径>', engine='xlrd')
frames=[]
for s in xl.sheet_names:
    df=xl.parse(s, header=1, dtype=str)
    df=df[df['部门代码'].notna()]
    frames.append(df)
a=pd.concat(frames, ignore_index=True)
print('岗位数', len(a))

ALL_CATS = set(cat2disc.keys())
ALL_NAMES = set(name2cat.keys())

# 覆盖率分析：岗位专业字段里的每个 token，能否被我们的库解释
covered_rows = 0
uncov_tokens = collections.Counter()
tok_total = 0
for m in a['专业'].astype(str):
    toks = re.split(r'[、，,；;/\s]+', m)
    row_ok = False
    for t in toks:
        t = t.strip()
        if not t or len(t)<2: continue
        tok_total += 1
        # 去掉前置修饰
        t2 = re.sub(r'^[^：:]*[：:]', '', t)
        # 命中判断：是专业类 / 是专业名 / 代码
        hit = (t2 in ALL_CATS or t2 in ALL_NAMES or re.fullmatch(r'\d{4,6}[TK]{0,2}', t2))
        if not hit:
            # 尝试"XX类"剥离
            base = re.sub(r'类$','',t2)
            hit2 = any(base and (base in n or n in base) for n in list(ALL_NAMES)[:0])
            uncov_tokens[t] += 1
        else:
            row_ok = True
    if row_ok: covered_rows += 1

print(f'岗位行可解释率: {covered_rows}/{len(a)} = {covered_rows/len(a)*100:.1f}%')
print('未覆盖 token top 40:')
for k,v in uncov_tokens.most_common(40):
    print(' ', v, '|', k[:50])
