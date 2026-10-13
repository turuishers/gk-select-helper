import json, re, io, collections
import pandas as pd

db = json.load(io.open('_major_db.json', encoding='utf-8'))
bk, grad = db['benke'], db['yanjiu']
custom = json.load(io.open('_gk_custom.json', encoding='utf-8'))
custom = {k:v for k,v in custom.items() if not k.startswith('_')}

# ---- 构建三张索引表 ----
# 1) 专业名 -> 信息（本科优先）
major2info = {}
for r in bk:
    major2info.setdefault(r['name'], {'cat':r['cat'],'disc':r['disc'],'level':'本科','code':r['code']})
for r in grad:
    major2info.setdefault(r['name'], {'cat':r.get('cat','') or r['name'][:2]+'类','disc':r['disc'],'level':'研究生','code':r['code']})

# 2) 专业类 -> 门类（教育部正式类）
cat2disc = {}
for r in bk: cat2disc[r['cat']] = r['disc']
# 研究生一级学科也可作为"类"的等价物
for r in grad:
    cat2disc.setdefault(r['name']+'类', r['disc'])

# 3) 国考自定义类 -> 包含的专业名列表 + 推断门类
gkcustom = {}
for cat, names in custom.items():
    gkcustom[cat] = names

# ---- 反查：给用户输入的专业，返回 门类 + 所属类 + 可能被国考归入的自定义类 ----
def resolve(major):
    m = str(major).strip()
    info = major2info.get(m)
    info_cat = info['cat'] if info else ''
    info_disc = info['disc'] if info else ''
    # 该专业被哪些国考自定义类收录
    gk_hits = [cat for cat, names in gkcustom.items() if m in names]
    return {'major':m,'cat':info_cat,'disc':info_disc,'code':info['code'] if info else '','gkCustom':gk_hits}

# ---- 覆盖率验证 ----
xl = pd.ExcelFile(r'<填入本机上 2026国考.xls 的完整路径>', engine='xlrd')
frames=[]
for s in xl.sheet_names:
    df=xl.parse(s, header=1, dtype=str); df=df[df['部门代码'].notna()]; frames.append(df)
a=pd.concat(frames, ignore_index=True)

ALL_KNOWN_CATS = set(cat2disc.keys()) | set(gkcustom.keys())
ALL_NAMES = set(major2info.keys())

def norm_tok(t):
    t = t.strip()
    t = re.sub(r'^[^：:]{0,12}[：:]', '', t)     # 去"研究生："前缀
    t = re.sub(r'[（(][^）)]*[）)]', '', t)      # 去括号备注
    t = re.sub(r'^\d{4,6}[TK]{0,2}', '', t)     # 去前置代码
    t = re.sub(r'[TK]$','',t).strip()
    return t

covered=0; uncov=collections.Counter()
for m in a['专业'].astype(str):
    toks=[x for x in re.split(r'[、，,；;/]+', m) if x.strip()]
    ok=False
    for t in toks:
        n=norm_tok(t)
        if not n or len(n)<2: continue
        if n in ALL_KNOWN_CATS or n in ALL_NAMES: ok=True; break
        # "XX类"去掉类字再比
        if n.endswith('类') and n[:-1] in ALL_NAMES: ok=True; break
        # 数字代码
        if re.fullmatch(r'\d{4,6}', n): ok=True; break
    if ok: covered+=1
    else:
        for t in toks:
            n=norm_tok(t)
            if n and len(n)>=2: uncov[n]+=1

print(f'覆盖率: {covered}/{len(a)} = {covered/len(a)*100:.1f}%')
print('剩余未覆盖 top 30:')
for k,v in uncov.most_common(30): print(' ',v,'|',k[:45])

io.open('_final_db.json','w',encoding='utf-8').write(json.dumps({
  'major2info':major2info,'cat2disc':cat2disc,'gkcustom':gkcustom
}, ensure_ascii=False))
print('major2info:', len(major2info), 'cat2disc:', len(cat2disc), 'gkcustom:', len(gkcustom))
