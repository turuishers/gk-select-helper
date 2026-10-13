# -*- coding: utf-8 -*-
"""
国考个性化选岗报告生成器

============================================================
正确用法（必须先走完工具里的三步）
============================================================
  第一步  打开《国考选岗助手-<年份>.html》，在左侧「个人档案」里填学生条件
  第二步  在结果列表里按偏好勾选筛选（层级/性质/地点/竞争…）
  第三步  逐个打开感兴趣的岗位抽屉，给主观项（工作内容/强度/薪酬/文化）打分
          —— 这一步是"人工校准"，不做的话报告就只是机器默认分排序
  第四步  点右上角「导出配置」，存成  xxx-选岗配置-日期.json
  第五步  运行本脚本：python 生成选岗报告.py 该json文件路径

  为什么必须这么做：
  工具里的筛选条件、全局默认分、以及你逐个岗位的手工微调，
  都存在浏览器 localStorage 里，脚本读不到。
  导出配置文件 = 把这套"你亲手调过的完整状态"交出来，
  报告才能忠实反映你的判断，而不是机器默认值。

============================================================
批量模式（可选）
============================================================
  如果一次要出多个学生的报告，把各自的 json 放到一个目录，
  然后运行：python 生成选岗报告.py 该目录路径
  脚本会自动为每个 json 出一份报告。
============================================================
"""
import json
import os
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "选岗报告"


def _year_of(p):
    """从文件名里抠出 4 位年份，取不到算 0"""
    m = re.search(r"(\d{4})", Path(p).stem)
    return int(m.group(1)) if m else 0


def pick_html():
    """自动挑选用哪个工具页面。

    规则：在同目录的「国考选岗助手*.html」里，优先取文件名带 4 位年份的，
    年份最大的胜出（例如 国考选岗助手-2027.html > 国考选岗助手.html）。
    子目录（如 备份/）不参与，所以历年备份不会被误选。
    想手工指定，就设环境变量 GK_HTML，例如（CMD）：
        set GK_HTML=国考选岗助手.html
    """
    forced = os.environ.get("GK_HTML")
    if forced:
        p = Path(forced)
        if not p.is_absolute():
            p = BASE / p
        if p.exists():
            return p
        print("[警告] GK_HTML 指定的文件不存在，改用自动挑选：%s" % p)

    cands = [p for p in BASE.glob("国考选岗助手*.html") if p.is_file()]
    if not cands:
        return None
    cands.sort(key=lambda p: (_year_of(p), p.stat().st_mtime), reverse=True)
    return cands[0]


HTML = pick_html()
DATA_YEAR = _year_of(HTML) if HTML else 2026
PREV_YEAR = DATA_YEAR - 1

# ---- 无参数时的兜底：把要处理的配置文件路径写在这里，或直接命令行传参 ----
DEFAULT_CONFIGS = [
    # BASE / "张三-选岗配置-2026-10-13.json",
]


# ============================================================
# 以下为生成逻辑，一般不需要改动
# ============================================================

DIM_NAMES = {
    "major": "专业匹配度", "limit": "报考条件限制", "content": "工作内容与兴趣",
    "diff": "上岸难度", "platform": "部门平台", "pace": "工作强度",
    "pay": "薪酬福利", "place": "工作地点", "culture": "单位文化",
}
DIM_ORDER = ["major", "limit", "diff", "platform", "place", "content", "pace", "pay", "culture"]


def collect_configs(argv):
    """把命令行参数展开成配置文件列表（支持文件 / 目录 / 通配符）"""
    items = []
    for a in argv:
        p = Path(a)
        if p.is_dir():
            items += sorted(p.glob("*.json"))
        elif p.exists():
            items.append(p)
        else:
            # 当作通配符再试一次
            items += sorted(BASE.glob(a))
    if not items:
        items = [p for p in DEFAULT_CONFIGS if Path(p).exists()]
    return items


def load_config(path):
    """读取工具导出的配置，做基本校验"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("type") != "gk-profile":
        raise ValueError("不是工具导出的配置文件（缺少 type: gk-profile）：%s" % path)
    P = raw.get("P") or {}
    F = raw.get("F") or {}
    MS = raw.get("MS") or {}
    PJS = raw.get("PJS") or {}
    if not P.get("major"):
        raise ValueError("配置里没有专业信息，无法筛选：%s" % path)
    return {"P": P, "F": F, "MS": MS, "PJS": PJS, "raw": raw}


def run_all(configs):
    OUT_DIR.mkdir(exist_ok=True)
    if HTML is None:
        print("[错误] 同目录下没找到「国考选岗助手*.html」。")
        print("       请确认本脚本和工具网页放在同一个文件夹里。")
        return
    if not configs:
        print("没有找到配置文件。")
        print("请先在工具里走完三步，点「导出配置」，再把 json 路径传给本脚本。")
        return

    print("使用工具页面：%s（%d 年度）" % (HTML.name, DATA_YEAR))
    print("配置文件：%d 个" % len(configs))
    print("")

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(HTML.as_uri())
        pg.wait_for_timeout(5500)

        for cfg_path in configs:
            try:
                cfg = load_config(cfg_path)
            except Exception as e:
                print("[跳过] %s -> %s" % (cfg_path.name, e))
                continue

            P = cfg["P"]
            name = (P.get("major") or "") + "-" + cfg_path.stem[:20]
            # 优先用配置里的备注名 / 文件名里的姓名
            display = P.get("name") or _name_from_file(cfg_path)
            print("=" * 60)
            print("正在生成：%s" % display)

            data = pg.evaluate(
                """(cfg) => {
                const {P:srcP, F:srcF, MS:srcMS, PJS:srcPJS} = cfg;

                // 1. 还原个人档案（用工具的 merge 语义，就地改数组）
                for (const k in P) {
                    const v = srcP[k];
                    if (v == null) continue;
                    if (Array.isArray(P[k])) { P[k].length = 0; v.forEach(x => P[k].push(x)); }
                    else P[k] = v;
                }
                // 2. 还原筛选条件（这是第二步"按偏好筛岗"的结果）
                for (const k in F) {
                    const v = srcF[k];
                    if (v == null) continue;
                    if (Array.isArray(F[k])) { F[k].length = 0; v.forEach(x => F[k].push(x)); }
                    else F[k] = v;
                }
                // 3. 还原全局默认分（第三步里调过的"所有岗位通用偏好"）
                for (const k in MS) { if (srcMS[k] != null) MS[k] = srcMS[k]; }

                // 4. 还原逐岗人工打分（第三步的核心产物）
                PJS = {};
                for (const k in (srcPJS || {})) PJS[k] = Object.assign({}, srcPJS[k]);

                // 5. 补一遍专业识别，保证与工具界面一致
                const g = P.major ? guessMajor(P.major) : null;
                if (g) { P.majorCat = g.cat || ''; P.majorDisc = g.disc || '';
                         P.majorGk = g.gkCustom || []; P.majorExact = !!g.exact; }

                keyword = '';

                // 6. 筛选 + 评分（评分会读 msOf，逐岗覆盖自动生效）
                const list = filter().map(j => {
                    const s = calcScore(j);
                    const key = jobKey(j);
                    return {j, total: s.total, raw: s.raw,
                            manual: !!PJS[key]};
                }).sort((a, b) => b.total - a.total);

                const top = list.slice(0, 5);
                const alt = list.slice(5, 15);

                const pick = (x) => ({
                    code: x.j.code, dept: x.j.dept, bureau: x.j.bureau,
                    title: x.j.title, level: x.j.level, nature: x.j.nature,
                    prov: x.j.prov, workPlace: x.j.workPlace, num: x.j.num,
                    prevNum: x.j.prevNum, edu: x.j.edu, degree: x.j.degree,
                    major: x.j.major, party: x.j.party, exp: x.j.exp,
                    sg: x.j.sg, fresh: x.j.fresh, ratio: x.j.ratio,
                    attr: x.j.attr, exam: x.j.exam, dist: x.j.dist,
                    proTest: x.j.proTest, settle: x.j.settle,
                    intro: x.j.intro, remark: x.j.remark,
                    total: x.total, raw: x.raw, manual: x.manual,
                });

                return {
                    recognized: g,
                    dataCount: DATA.length,
                    totalMatched: list.length,
                    manualCount: Object.keys(PJS).length,
                    manualInTop: top.filter(x => x.manual).length,
                    filters: {F: JSON.parse(JSON.stringify(F)), MS: JSON.parse(JSON.stringify(MS))},
                    top: top.map(pick),
                    alt: alt.map(pick),
                };
            }""",
                cfg,
            )
            data["dataYear"] = DATA_YEAR
            data["prevYear"] = PREV_YEAR
            print("  专业识别 :", data["recognized"])
            print("  可报岗位 :", data["totalMatched"])
            print("  岗位表   : %d 年度 · %s 个岗位"
                  % (DATA_YEAR, format(data.get("dataCount") or 0, ",")))
            print("  人工打分 :", data["manualCount"], "个岗位（其中前5名里", data["manualInTop"], "个）")
            md = build_report(cfg, data, display)
            fn = OUT_DIR / ("%s-选岗报告.md" % display)
            fn.write_text(md, encoding="utf-8")
            print("  已输出   :", fn.name)

        b.close()


def _name_from_file(p):
    """从文件名里抠出学生名：'张三-选岗配置-2026-10-13.json' -> '张三'"""
    s = Path(p).stem
    s = re.sub(r"-?选岗配置.*$", "", s).strip("-_ ")
    return s or Path(p).stem


def _fmt_filters(f):
    """把筛选条件翻译成人话"""
    out = []
    F = f.get("F") or {}
    labels = {
        "level": "机构层级", "nature": "机构性质", "exam": "考试类别",
        "attr": "职位属性", "dept": "招录部门", "ratio": "面试比例",
        "dist": "工作地点类型", "proTest": "专业能力测试",
    }
    for k, cn in labels.items():
        v = F.get(k)
        if isinstance(v, list) and v:
            out.append("%s：%s" % (cn, "、".join(v)))
    if F.get("numMin"):
        out.append("招考人数不少于 %s 人" % F["numMin"])
    return out


def _fmt_ms(ms):
    """把全局默认分翻译成人话（3 分=默认中等）"""
    items = []
    for k in ["content", "pace", "pay", "culture"]:
        v = ms.get(k, 3)
        if v != 3:
            items.append("%s %s" % (DIM_NAMES[k], v))
    return items


def _comment(rec):
    """为单个岗位生成点评：优势 + 需留意"""
    j, raw = rec, rec["raw"]
    pros, cons = [], []

    # 人工调过分的岗位，第一句就点明
    if rec.get("manual"):
        pros.append("**这个岗位你在工具里单独打过分数**，排序已按你的判断走")

    # 专业匹配 —— 按实际得分给不同措辞，不能笼统说"可报"
    m = raw["major"]
    if m >= 4.5:
        pros.append("专业要求与你的专业**完全对口**，报名资格最稳")
    elif m >= 3.5:
        pros.append("专业直接命中岗位要求，**资格没问题**")
    elif m >= 2.5:
        pros.append("专业属于要求的大类范围，可报（**建议核对岗位专业列表确认**）")
    else:
        cons.append("**专业匹配度偏低，务必先确认自己是否在要求范围内**")

    # 报考门槛
    if raw["limit"] >= 3.5:
        pros.append("设有一定门槛（%s），**符合条件的人相对少**" % _limit_desc(j))
    elif raw["limit"] <= 2.2:
        cons.append("几乎无附加门槛，**报名人数可能较多**")

    # 上岸难度
    if raw["diff"] >= 4:
        pros.append("招考 **%d 人**，在国考里属于招得多的，机会相对大" % j["num"])
    elif raw["diff"] <= 2.6:
        cons.append("**仅招 %d 人**，竞争会很激烈" % j["num"])

    # 平台
    if raw["platform"] >= 4:
        pros.append("%s 单位，平台高、发展空间大" % j["level"])
    elif raw["platform"] <= 2:
        cons.append("基层单位，需考虑长期发展预期")

    # 地点
    if raw["place"] >= 4:
        pros.append("工作地点 %s，城市条件好" % j["workPlace"])
    elif raw["place"] <= 2.5:
        cons.append("工作地点 %s，**要确认自己能接受当地生活**" % j["workPlace"])

    # 专业能力测试：这是实打实的额外准备
    if j["proTest"] == "是":
        cons.append("面试阶段组织**专业能力测试**，需额外准备")

    # 备注里的硬性要求（用更精确的句式匹配，避免误报）
    r = str(j["remark"] or "")
    if re.search(r"服务期|最低服务年限|服务年限", r):
        cons.append("备注含**最低服务年限**约定，务必看清")
    if re.search(r"法律职业资格|司考|司法考试", r):
        cons.append("要求**法律职业资格**")
    if re.search(r"英语(四级|六级|专业八级|专八)|CET-?[46]|雅思|托福", r):
        cons.append("有**英语等级**硬性要求")
    if re.search(r"注册会计师|CPA|ACCA|中级会计|税务师|资格证", r):
        cons.append("要求相关**职业资格证书**")
    if re.search(r"驻外|艰苦边远|经常出差|常年出差", r):
        cons.append("涉及**驻外或出差**，需评估接受度")
    if re.search(r"五年|5年", r) and "服务" in r:
        cons.append("有**五年服务期**约定")

    if not pros:
        pros.append("各项条件较均衡")
    if not cons:
        cons.append("未从数据中发现明显短板，建议打开职位详情确认")
    return pros[:4], cons[:4]


def _limit_desc(j):
    parts = []
    if j["party"] and "不限" not in str(j["party"]):
        parts.append(str(j["party"]))
    if j["exp"] and j["exp"] not in ("无限制", "无要求"):
        parts.append(j["exp"] + "基层经验")
    if j["sg"]:
        parts.append("服务基层项目")
    return "、".join(parts) if parts else "学历学位"


def build_report(cfg, data, name):
    L = []
    push = L.append
    st = cfg["P"]
    g = data["recognized"] or {}

    push("# %s · 国考选岗报告\n" % name)
    push("> 依据 %d 年国考职位表（%s 个岗位）｜ 生成时间 %s\n"
         % (data.get("dataYear") or DATA_YEAR,
            format(data.get("dataCount") or 0, ","),
            __import__("datetime").datetime.now().strftime("%Y-%m-%d")))
    push("> 本报告的筛选条件与岗位评分，来自你在《国考选岗助手》里的**实际操作结果**（已导出）\n")

    # 一、你的条件
    push("## 一、你的报考条件\n")
    push("| 项目 | 内容 |")
    push("|------|------|")
    push("| 学历 | %s |" % (st.get("edu") or "不限"))
    push("| 学位 | %s |" % (st.get("degree") or "不限"))
    push("| 所学专业 | **%s** |" % st.get("major", ""))
    if g:
        push("| 专业识别 | %s 门类 → %s%s |" % (
            g.get("disc", "?"), g.get("cat", "?"),
            ("（对应国考类：%s）" % "、".join(g.get("gkCustom") or [])) if g.get("gkCustom") else ""))
    push("| 政治面貌 | %s |" % ("、".join(st.get("party") or []) or "不限"))
    push("| 基层工作年限 | %s |" % (st.get("exp") or "不限"))
    push("| 服务基层项目 | %s |" % ("、".join(st.get("sg") or []) or "无"))
    push("| 应往届 | %s |" % (st.get("fresh") or "不限"))
    push("| 意向省份 | %s |" % ("、".join(st.get("provs") or []) or "全国不限"))
    push("")

    # 附加筛选条件
    extra = _fmt_filters(data.get("filters") or {})
    if extra:
        push("**在此基础上，你还额外筛掉了不想要的岗位：**\n")
        for x in extra:
            push("- %s" % x)
        push("")

    ms = _fmt_ms((data.get("filters") or {}).get("MS") or {})
    if ms:
        push("**你对主观项的通用偏好**（未单独打分的岗位沿用这个）：%s\n" % "、".join(ms))

    push("**筛选结果：满足以上全部条件的岗位共 %d 个。**" % data["totalMatched"])
    mc = data.get("manualCount") or 0
    if mc:
        push("其中你在工具里**逐个打开、亲手调过分**的有 %d 个。" % mc)
    else:
        push("**注意：配置里没有逐岗人工打分的记录。**"
             "如果你确实做过第三步，请确认是在同一个浏览器里操作的、并重新导出一次配置。")
    push("")

    # 边界：0 个岗位
    if data["totalMatched"] == 0:
        push("> ⚠️ **当前条件下没有找到可报岗位。**\n")
        push("常见原因和对策：\n")
        push("| 可能原因 | 怎么办 |")
        push("|---------|--------|")
        push("| 省份限制太严 | 先取消省份勾选（= 全国不限）看看有哪些能报 |")
        push("| 筛选条件叠太多 | 第二步勾的层级/性质/竞争条件太多，先逐项取消试试 |")
        push("| 学历填得太高 | 确认是否该填「本科及以上」而非「仅限本科」 |")
        push("| 专业写法不同 | 试试填**专业全称**，或换用专业大类名（如「计算机类」） |")
        push("| 政治面貌/基层年限 | 检查是否勾选了自己不符合的项 |")
        push("")
        push("建议先放宽条件，确认能报的岗位范围，再逐步加限制。\n")
        push("---\n")
        push("> 本报告由《国考选岗助手》导出配置自动生成。\n")
        return "\n".join(L)

    # 二、推荐岗位
    push("## 二、推荐岗位（前 5 个）\n")
    push("以下岗位按综合评分排序，是你**在工具里筛完之后、剩下的岗位中条件最好的 5 个**。\n")
    for i, rec in enumerate(data["top"], 1):
        push(render_job(i, rec))
    push("")

    # 三、备选
    if data["alt"]:
        push("## 三、备选岗位（第 6～%d 个）\n" % (5 + len(data["alt"])))
        push("如果上面的岗位有不符合预期的地方，可以从这里继续看。\n")
        push("| # | 岗位 | 部门 | 地点 | 招考 | 评分 | 手调 |")
        push("|---|------|------|------|------|------|------|")
        for i, rec in enumerate(data["alt"], 6):
            push("| %d | %s | %s | %s | %d 人 | **%.2f** | %s |" % (
                i, rec["title"][:22], rec["dept"][:12], rec["workPlace"][:10],
                rec["num"], rec["total"], "✓" if rec.get("manual") else ""))
        push("")

    # 四、建议
    push("## 四、给你的建议\n")
    for block in advice(data):
        push(block)
    push("")

    push("---\n")
    push("> 本报告由《国考选岗助手》自动生成。评分是基于 9 个维度的**参考排序**，不构成报考建议。")
    push("> 分数只用来帮你缩小范围，**最终选择请结合职位详情、单位情况和自身意愿决定**。\n")
    return "\n".join(L)


def render_job(no, rec):
    L = []
    push = L.append
    pros, cons = _comment(rec)

    push("### %d. %s%s\n" % (no, rec["title"], "  ★已人工打分" if rec.get("manual") else ""))
    push("**综合评分 %.2f / 10**\n" % rec["total"])
    push("| | |")
    push("|------|------|")
    push("| 招录部门 | %s |" % rec["dept"])
    push("| 用人司局 | %s |" % rec["bureau"])
    push("| 职位代码 | %s |" % rec["code"])
    push("| 招考人数 | **%d 人**%s |" % (
        rec["num"], ("（%d 年 %d 人）" % (PREV_YEAR, rec["prevNum"])) if rec.get("prevNum") else ""))
    push("| 机构层级 | %s |" % rec["level"])
    push("| 工作地点 | %s |" % rec["workPlace"])
    push("| 落户地点 | %s |" % (rec["settle"] or "—"))
    push("| 学历要求 | %s |" % rec["edu"])
    push("| 专业要求 | %s |" % rec["major"][:80])
    push("| 政治面貌 | %s |" % rec["party"])
    push("| 基层年限 | %s |" % rec["exp"])
    push("| 面试比例 | %s |" % rec["ratio"])
    push("| 专业测试 | %s |" % rec["proTest"])
    push("")
    if rec["intro"]:
        push("**工作内容**：%s\n" % rec["intro"])
    push("**评分明细**\n")
    push("| 维度 | 得分 |")
    push("|------|------|")
    for k in DIM_ORDER:
        push("| %s | %.1f |" % (DIM_NAMES[k], rec["raw"][k]))
    push("")
    push("**优势**")
    for x in pros:
        push("- %s" % x)
    push("")
    push("**需要留意**")
    for x in cons:
        push("- %s" % x)
    push("")
    return "\n".join(L)


def advice(data):
    out = []
    top = data["top"]
    n = data["totalMatched"]
    if not top:
        return ["当前条件下没有找到可报岗位，建议放宽省份或筛选条件后重新筛选。"]

    out.append("**1. 你的可选范围**\n")
    if n < 20:
        out.append("筛完之后符合条件的岗位只有 **%d 个**，范围很窄。这说明你的条件（尤其是专业 + 省份 + 筛选条件的组合）限制较强。"
                   "建议：可以先放宽一两个筛选条件，看看有没有被误筛掉的机会。\n" % n)
    elif n < 200:
        out.append("筛完之后符合条件的岗位有 **%d 个**。范围适中，上面 5 个是其中的优选，建议逐个了解。\n" % n)
    else:
        out.append("筛完之后符合条件的岗位有 **%d 个**，可选范围很宽。这说明你条件限制少，"
                   "相应地**竞争也会更激烈**（门槛低 = 报的人多）。\n" % n)

    mc = data.get("manualCount") or 0
    out.append("**2. 关于你的手工打分**\n")
    if mc:
        out.append("你在工具里对 **%d 个**岗位做过单独调整，前 5 名里有 **%d 个**是手调过的。"
                   "这些岗位的排序反映的是**你自己的判断**，可信度最高。\n"
                   % (mc, data.get("manualInTop") or 0))
        if (data.get("manualInTop") or 0) < 5:
            out.append("还有几个推荐岗位走的是通用默认分（工作内容/强度/薪酬/文化按中等算），"
                       "**如果你对这几点有明确偏好，建议回去打开这几个岗位再调一次，排序会更准。**\n")
    else:
        out.append("配置里没有逐岗手工打分的记录，**本次排序全部由机器默认分算出来**，"
                   "其中 4 个主观项（工作内容、强度、薪酬、文化）都按中等分处理。\n")
        out.append("**强烈建议**：回到工具里，对你感兴趣的几个岗位逐个打开、调一次主观分，再重新导出配置生成报告。\n")

    best = top[0]
    out.append("**3. 最值得优先了解的**\n")
    out.append("第 1 个「%s」（%.2f 分）综合条件最好。" % (best["title"], best["total"]))
    if best["raw"]["diff"] <= 2.6:
        out.append("但**只招 %d 人，竞争会很激烈**，建议同时准备后面的备选。\n" % best["num"])
    else:
        out.append("招 %d 人，机会相对可观，建议优先深入了解。\n" % best["num"])

    out.append("**4. 下一步怎么做**\n")
    out.append("分数只能帮你排序，**不能替你决定**。建议按这个顺序推进：\n")
    out.append("1. 上面 5 个岗位，逐个去查**职位简介和部门情况**")
    out.append("2. 了解每个岗位**所在地的生活条件**（房价、通勤、离家远近）")
    out.append("3. 如果对某个岗位有额外的了解（比如待遇好、要经常出差），"
               "**回到工具里打开它单独调整分数**，重新导出配置、重新出报告")
    out.append("4. 最后按**你自己的判断**确定 1～2 个主攻方向\n")

    out.append("**5. 关于本报告的评分**\n")
    out.append("评分由 9 个维度加权算出，其中 5 个是自动计算的（专业匹配、报考门槛、上岸难度、部门平台、工作地点），"
               "4 个是主观项（工作内容、强度、薪酬、文化），默认按中等分处理。")
    out.append("这次报告用的是**你导出时的真实状态**：筛选条件、通用偏好、逐岗手调都已包含在内。\n")
    return out


if __name__ == "__main__":
    configs = collect_configs(sys.argv[1:])
    if not configs:
        print(__doc__)
        print("=" * 60)
        print("用法：python 生成选岗报告.py <导出的配置文件.json>")
        print("提示：请先在《国考选岗助手》里走完三步，然后点右上角「导出配置」。")
        sys.exit(0)
    run_all(configs)
    print("\n全部完成，报告在：%s" % OUT_DIR)
