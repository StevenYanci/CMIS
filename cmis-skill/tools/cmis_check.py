#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMIS 方案自检器

用途：把 references/field-registry.md 的字段总账变成可执行检查，
     让"漏字段"从"靠记性"变成"会报错"。

用法：
    python cmis-skill/tools/cmis_check.py cases/某方案.md
    python cmis-skill/tools/cmis_check.py cases/某方案.md --verbose

退出码：0 = 无 FAIL；1 = 有 FAIL（必须修）；2 = 文件读取失败

严重度定义：
    FAIL  结构或算术硬错误，必须修正后才能交付
    WARN  字段未检出或存在风险，需人工确认（可能是等价表述）
    INFO  统计信息，供参考
"""

import argparse
import os
import re
import sys

# ---------------------------------------------------------------- 基础工具

CHAP_RE = re.compile(r"^#{2,3}\s*第\s*(\d+)\s*章", re.M)
D_RE = re.compile(r"D\d-\d{2}")
D_DEF_RE = re.compile(r"\*\*(D\d-\d{2})\*\*")
LIMIT_WORDS_HARD = ["绝版", "永不再有", "最后机会", "史上最", "全国唯一", "绝对最低"]
LIMIT_WORDS_SOFT = ["唯一", "第一", "最"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def chapters(text):
    """返回 {章号: 该章正文}，以及按出现顺序的章号列表。"""
    marks = [(int(m.group(1)), m.start()) for m in CHAP_RE.finditer(text)]
    out, order = {}, []
    for i, (num, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        if num in out:          # 重复章号：拼接，便于合并统计
            out[num] += "\n" + text[start:end]
        else:
            out[num] = text[start:end]
            order.append(num)
    return out, order


def num(s):
    """从单元格里抽出数字，兼容 **1,234** / ¥29 / 47% / 1.8 件。"""
    if s is None:
        return None
    t = re.sub(r"[*¥,\s]", "", str(s))
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group(0)) if m else None


def tables(block):
    """抽出 markdown 表格，返回 [(表头单元格列表, [行单元格列表...]), ...]"""
    out, cur = [], []
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            cur.append(cells)
        else:
            if len(cur) >= 2:
                out.append(cur)
            cur = []
    if len(cur) >= 2:
        out.append(cur)
    res = []
    for tb in out:
        header = tb[0]
        rows = [r for r in tb[1:] if not re.match(r"^[-:\s]+$", "".join(r))]
        res.append((header, rows))
    return res


def find_table(block, must_have, exclude=()):
    for header, rows in tables(block):
        h = "".join(header)
        if all(k in h for k in must_have) and not any(k in h for k in exclude):
            return header, rows
    return None, None


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, code, msg, hint=""):
        self.items.append((level, code, msg, hint))

    def fail(self, code, msg, hint=""):
        self.add("FAIL", code, msg, hint)

    def warn(self, code, msg, hint=""):
        self.add("WARN", code, msg, hint)

    def info(self, code, msg, hint=""):
        self.add("INFO", code, msg, hint)

    def counts(self):
        c = {"FAIL": 0, "WARN": 0, "INFO": 0}
        for lv, *_ in self.items:
            c[lv] += 1
        return c

    def dump(self, verbose):
        icon = {"FAIL": "✗", "WARN": "!", "INFO": "·"}
        for lv, code, msg, hint in self.items:
            if lv == "INFO" and not verbose:
                continue
            print(f"  {icon[lv]} [{lv:4}] {code}  {msg}")
            if hint and (lv != "INFO" or verbose):
                print(f"          → {hint}")
        c = self.counts()
        print(f"\n  合计：FAIL {c['FAIL']} / WARN {c['WARN']} / INFO {c['INFO']}")


# ---------------------------------------------------------------- 各项检查

def check_structure(text, ch, order, mode, rep):
    expect = list(range(1, 19))
    if mode in ("精简案", "急救案"):
        expect = list(range(1, 13)) + [16, 17, 18]
    missing = [n for n in expect if n not in ch]
    if missing:
        rep.fail("S01 章节完整性", f"缺第 {missing} 章", "按 templates.md 补齐，急救案可裁但不可乱序")
    else:
        rep.info("S01 章节完整性", f"{len(expect)} 章齐全，序列正常")

    dup = [n for n in order if order.count(n) > 1]
    if dup:
        rep.warn("S01b 章号重复", f"章号重复：{sorted(set(dup))}", "合并为单章，避免读者按章号找不到内容")

    parts = ["Part I", "Part II", "Part III"]
    if mode in ("全案", "标准案"):
        lack = [p for p in parts if p not in text]
        if lack:
            rep.fail("S02 三段式", f"缺 {lack}", "依据→决策→落地三段必须显式分段")
        else:
            rep.info("S02 三段式", "依据 / 决策 / 落地 分段齐全")


def check_basis_sections(ch, rep):
    """每册必须有「→ 决策含义」与「我们不知道什么」。"""
    for n in range(2, 9):
        blk = ch.get(n, "")
        if not blk:
            continue
        if "决策含义" not in blk:
            rep.fail(f"S03 D{n-1} 决策含义", f"第 {n} 章无「→ 决策含义」", "每册 3-5 条，带 D 编号，否则依据成摆设")
        if "不知道" not in blk:
            rep.fail(f"S04 D{n-1} 诚实节", f"第 {n} 章无「我们不知道什么」",
                     "只写有利信息会让后面所有数字虚高；写清缺什么 + 影响 + 替代判断")


def check_d_refs(text, rep):
    defined = set(D_DEF_RE.findall(text))
    used = D_RE.findall(text)
    if not defined:
        rep.fail("S05 依据编号", "全文没有形如 **D1-01** 的依据条目定义",
                 "依据必须编号，否则第 1 章结论与第 9 章符号来源无法追溯")
        return
    undefined = sorted({u for u in used if u not in defined})
    if undefined:
        rep.fail("S05 依据编号", f"引用了未定义的编号：{undefined}", "补定义，或改为已有编号")

    # 每册至少 1 条被"真正引用"（出现次数 ≥2：一次定义，一次引用）
    by_book = {}
    for d in defined:
        book = d.split("-")[0]
        cited = used.count(d) >= 2
        by_book.setdefault(book, [0, 0])
        by_book[book][0] += 1
        by_book[book][1] += 1 if cited else 0
    dead = [b for b, (tot, c) in by_book.items() if tot and c == 0]
    detail = " ".join(f"{b}:{c}/{t}" for b, (t, c) in sorted(by_book.items()))
    if dead:
        rep.fail("S05b 依据未引用", f"{dead} 册没有任何被引用的依据", "整册未被引用=这册没影响任何决定，等于白写")
    else:
        rep.info("S05b 依据引用率", detail + "（被引用条数/定义条数）")
        weak = [b for b, (t, c) in by_book.items() if t and c / t < 0.4]
        if weak:
            rep.warn("S05c 依据引用偏弱", f"{weak} 册引用率 <40%（{detail}）",
                     "决策含义若从未被第1章或第9章引用，说明它只是记录，不是依据")
    per = {}
    for d in defined:
        per.setdefault(d.split("-")[0], 0)
        per[d.split("-")[0]] += 1
    rep.info("S05c 依据分布", " ".join(f"{k}:{v}条" for k, v in sorted(per.items())))


def check_aesthetic(ch, rep):
    blk = ch.get(3, "")
    if not blk:
        return
    total = 0.0
    found = False
    for header, rows in tables(blk):
        if "权重" not in "".join(header):
            continue
        for r in rows:
            if any("合计" in c for c in r):
                continue
            for c in r[1:3]:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", c)
                if m:
                    total += float(m.group(1))
                    found = True
                    break
        if found:
            break
    if not found:
        rep.warn("S06 审美权重", "第 3 章未检出带百分比的权重表", "字段 3-06 必填，合计须 100%")
    elif abs(total - 100) > 1:
        rep.fail("S06 审美权重", f"权重合计 {total:.0f}%（应为 100%）",
                 "权重不带依据=编的；合计不为 100%=结构比例无从推导")
    else:
        rep.info("S06 审美权重", f"合计 {total:.0f}%，通过")


def gate_b(ch, rep):
    """返回 (rows, ok) ；rows 为 [(名, 份额, 销量, 首批, 售价, 成本, 毛利率, 下限, 判定)]"""
    blk = ch.get(9, "")
    header, rows = find_table(blk, ["份额", "完全成本"])
    if not rows:
        rep.fail("S07 Gate B 表", "第 9 章未检出 Gate B 定量闸表", "字段 9-05 必填，8 列不可少")
        return []

    need = ["份额", "基准销量", "首批", "售价", "完全成本", "毛利率", "下限", "判定"]
    lack = [k for k in need if k not in "".join(header)]
    if lack:
        rep.fail("S14 列头", f"Gate B 表缺列：{lack}", "列头不得增删，校验器按列头核对")

    out = []
    for r in rows:
        if len(r) < 8:
            continue
        name = r[0]
        out.append((name, r[1], num(r[2]), num(r[3]), num(r[4]), num(r[5]), num(r[6]), num(r[7]), r[-1]))
    return out


def check_gate_b(rows, rep):
    if not rows:
        return
    share_total, qty_total, rev_total, gp_total = 0.0, 0.0, 0.0, 0.0
    limited = 0.0
    for name, share_cell, qty, first, price, cost, gm, floor, verdict in rows:
        if qty is None or price is None:
            continue
        qty_total += qty
        rev_total += qty * price
        if cost is not None:
            gp_total += qty * (price - cost)
            calc = (price - cost) / price
            if gm is not None and gm > 1:      # 表格里写的是 47 而非 0.47
                gm = gm / 100.0
            if gm is not None and abs(calc - gm) > 0.02:
                rep.fail("S09 毛利率算术",
                         f"{name}：标注 {gm:.0f}%，按售价与完全成本算得 {calc:.0%}",
                         "毛利率=(售价−完全成本)/售价；完全成本须含分成与损耗")
        if share_cell and "限量" in share_cell:
            limited += qty
            m = re.search(r"(\d[\d,]*)", share_cell)
            if m:
                cap = float(m.group(1).replace(",", ""))
                if qty > cap:
                    rep.fail("S10 限量约束", f"{name}：销量 {qty:,.0f} > 限量 {cap:,.0f}",
                             "限量款按限量数定产，不参与份额分配")
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", share_cell or "")
            if m:
                share_total += float(m.group(1))
        if verdict and "❌" in verdict:
            rep.info("S07b Gate B 判定", f"{name} 未过闸（应已说明处置）")

    if share_total and abs(share_total - 100) > 1.5:
        rep.fail("S07 份额合计", f"非限量款份额合计 {share_total:.1f}%（应为 100%）",
                 "份额是结构占比，Σ≠100% 会导致总件数与人均件数同时错（C4）")
    elif share_total:
        rep.info("S07 份额合计", f"{share_total:.1f}%，通过（限量 {limited:,.0f} 件另计）")

    return qty_total, rev_total, gp_total


def check_quant(ch, rows, qty_total, rep):
    blk = ch.get(10, "")
    if not blk:
        return
    # 决策人次
    d_base = None
    for header, trows in tables(blk):
        if "决策人次" not in "".join(header) and not any("决策人次" in "".join(r) for r in trows):
            continue
        for r in trows:
            if "决策人次" in r[0]:
                # 列序：低 / 基准 / 高（可能还有依据列）→ 取第 2 个数值列作基准
                vals = [num(c) for c in r[1:4]]
                vals = [v for v in vals if v and v > 1000]
                if len(vals) >= 2:
                    d_base = vals[1]
                elif vals:
                    d_base = vals[0]
                break
        if d_base:
            break
    # 人均件数（基准列，通常是第 3 列）
    people = None
    for header, trows in tables(blk):
        for r in trows:
            if "人均件数" in r[0] and len(r) >= 3:
                people = num(r[2])
                break
        if people:
            break

    if d_base and people and qty_total:
        actual = qty_total / d_base
        if abs(actual - people) > 0.15:
            rep.fail("S08 人均件数", f"标注 {people} 件/人，按 Σ销量÷决策人次 实得 {actual:.2f} 件/人",
                     "总件数 M 必须等于 Σ分SKU销量；差 10% 以上说明份额未归一化（C5）")
        elif not 1.4 <= actual <= 2.8:
            rep.warn("S08 人均件数", f"实得 {actual:.2f} 件/人，超出模型校验区间 1.6-2.6", "给出解释或复核份额")
        else:
            rep.info("S08 人均件数", f"{actual:.2f} 件/人，与标注一致")

    # 分波去化合计
    for header, trows in tables(blk):
        if "占比" not in "".join(header):
            continue
        tot = 0.0
        hit = False
        for r in trows:
            for c in r:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", c)
                if m:
                    tot += float(m.group(1))
                    hit = True
                    break
        if hit and abs(tot - 100) > 1.5:
            rep.fail("S15 分波占比", f"分波去化占比合计 {tot:.0f}%（应为 100%）", "去化路径不闭合=有一批货没有出口")
        elif hit:
            rep.info("S15 分波占比", f"{tot:.0f}%，通过")
        break

    if "对账" not in blk and "一致" not in blk:
        rep.warn("S16 对账声明", "第 10 章未见与第 1 章的数值对账说明", "字段 10-09：明写流水/毛利一致")


def check_headline(ch, rows, rev_total, gp_total, rep):
    blk = ch.get(1, "")
    if not blk:
        return
    rev_line = gp_line = ""
    # 只在"以 流水/毛利 开头单元格"的行里取值，避免被正文中顺带提到"流水"的行干扰
    for line in blk.splitlines():
        if not line.strip().startswith("|"):
            continue
        first = line.strip().strip("|").split("|")[0].strip("* ")
        if first == "流水":
            rev_line = line
        if first == "毛利":
            gp_line = line
    if rev_total:
        nums = [num(x) for x in re.findall(r"[¥]\s*([\d,]+)\s*万", rev_line)]
        nums = [n for n in nums if n]
        if not nums:
            rep.warn("S17 第1章流水", "未在第 1 章解析到「¥X 万」形式的流水", "字段 1-08")
        elif not any(abs(n - rev_total / 1e4) / (rev_total / 1e4) < 0.02 for n in nums):
            rep.fail("S17 第1章流水",
                     f"第 1 章流水 {nums} 万，第 9 章明细合计 {rev_total/1e4:,.0f} 万",
                     "同一份方案两套数，客户一问就崩（C1）")
        else:
            rep.info("S17 第1章流水", f"与明细一致（{rev_total/1e4:,.0f} 万）")
    if gp_total and gp_line:
        nums = [num(x) for x in re.findall(r"[¥]\s*([\d,]+)\s*万", gp_line)]
        nums = [n for n in nums if n]
        if nums and not any(abs(n - gp_total / 1e4) / max(gp_total / 1e4, 1) < 0.05 for n in nums):
            rep.fail("S18 第1章毛利", f"第 1 章毛利 {nums} 万，明细合计 {gp_total/1e4:,.0f} 万", "（C2）")


def check_leak(ch, rep):
    """依据部不得出现具体 SKU 提案。只抓"品牌化款式名"（带「」《》或 ≥6 字），
    品类泛称（毛巾/T恤/钥匙扣）允许出现在依据部——依据本来就要指向品类。"""
    blk9 = ch.get(9, "")
    names = set()
    header, rows = find_table(blk9, ["象限", "SKU"])
    if rows:
        for r in rows:
            if len(r) >= 4:
                for n in re.split(r"[、,，/]", r[3]):
                    n = n.strip().strip("* ")
                    branded = ("「" in n or "《" in n or len(n) >= 6)
                    if branded and len(n) >= 3:
                        names.add(n.strip("「」《》"))
    if not names:
        rep.info("S11 依据部泄漏", "未从第 9 章解析到品牌化 SKU 名，跳过")
        return
    hits = []
    for n in range(2, 9):
        blk = ch.get(n, "")
        for nm in names:
            if nm and nm in blk:
                hits.append(f"第{n}章: {nm}")
    if hits:
        rep.warn("S11 依据部泄漏", f"依据部出现品牌化 SKU 名 {len(hits)} 处：{'；'.join(hits[:6])}",
                 "品类/工艺方向可以写，具体款式名属流程倒置")
    else:
        rep.info("S11 依据部泄漏", "依据部（第 2-8 章）未出现品牌化 SKU 名")


def check_words(text, rep):
    """极限词检查。跳过"禁用清单/自查"语境——列举禁忌词不算违规。"""
    exempt = ("禁用", "禁 ", "不得", "不可", "避免", "极限词", "违规", "自查", "红线", "禁「", "黑名单")
    hard_hits, soft_hits = [], {}
    for line in text.splitlines():
        if any(k in line for k in exempt):
            continue
        for w in LIMIT_WORDS_HARD:
            if w in line:
                hard_hits.append(w)
        for w in ("唯一", "史上", "最强"):
            if w in line:
                soft_hits[w] = soft_hits.get(w, 0) + 1
    hard_hits = sorted(set(hard_hits))
    if hard_hits:
        rep.fail("S12 极限词", f"出现违规/高风险表述：{hard_hits}",
                 "只写可验证事实（如「2026 年鸟巢最后一场」），禁「绝版/永不再有/最后机会」")
    if soft_hits:
        rep.warn("S12b 极限词（软）", f"出现 {soft_hits}", "逐处确认是否可被广告法认定为绝对化用语")


def check_appendix(ch, rep):
    blk = ch.get(18, "")
    if not blk:
        return
    for tag in ("附录 A", "附录 B", "附录 C"):
        if tag not in blk:
            rep.fail("S13 附录", f"第 18 章缺 {tag}", "附录 A 词库 / B 工艺 / C Top3 执行包，缺一不可")
    if "反向 Prompt" not in blk and "反向" not in blk:
        rep.warn("S13b 执行包", "附录 C 未见「反向 Prompt」", "Top3 执行包需 PART1 中文 brief + PART2 正向 + PART3 反向")


# 关键字段探针：只做 WARN，用于提示"可能漏了"
PROBES = [
    (1, "1-11", ["依据索引"], "第 1 章缺依据索引表"),
    (2, "2-07", ["应援色"], "缺应援色（没有也应写「无」）"),
    (2, "2-11", ["票价"], "缺票价结构，客单价无从校准"),
    (2, "2-13", ["缺口"], "缺 IP 资产缺口表"),
    (3, "3-05", ["组织形态"], "缺组织形态判定，运营打法无依据"),
    (3, "3-09", ["禁用", "黑名单"], "缺禁用黑名单"),
    (3, "3-10", ["平台"], "缺平台分布"),
    (4, "4-07", ["时长"], "缺时间段表（陈列动线与补货时点的唯一依据）"),
    (4, "4-10", ["场次"], "缺场次结构（多场连开时必填）"),
    (5, "5-05", ["六维"], "缺场馆 IP 六维评分"),
    (5, "5-08", ["档期"], "缺档期结构判定"),
    (6, "6-01", ["决策链"], "缺五方决策链"),
    (6, "6-04", ["T-"], "缺报批倒排节点"),
    (6, "6-06", ["分成"], "缺分成比例（直接影响第 12 章成本）"),
    (6, "6-10", ["Plan B"], "缺 Plan B 触发条件"),
    (7, "7-01", ["自带"], "缺「现场自带货」判定——谢霆锋型错误的根源"),
    (7, "7-08", ["独占"], "缺我方独占性论证"),
    (8, "8-02", ["检索日期"], "趋势结论未标检索日期（超 90 天即过期）"),
    (8, "8-07", ["保底"], "缺保底品类确认"),
    (9, "9-02", ["符号"], "缺符号推导清单"),
    (9, "9-03", ["三问"], "缺差异化三问记录"),
    (9, "9-08", ["暗纹", "编号", "彩蛋"], "缺高级稀缺性工艺"),
    (10, "10-05", ["敏感"], "缺敏感性分析"),
    (10, "10-07", ["返单", "λ"], "缺长尾与返单计划"),
    (11, "11-04", ["L1", "降级"], "缺极限交期降级方案"),
    (11, "11-05", ["锁货"], "缺锁货优先级"),
    (12, "12-02", ["校准", "竞品"], "缺竞品/历史定价校准"),
    (12, "12-06", ["敏感"], "缺分成敏感性"),
    (13, "13-02", ["色"], "缺色彩规范"),
    (14, "14-04", ["文案"], "缺分场景文案"),
    (15, "15-02", ["T-14", "T+7", "首发"], "缺首发节奏时间轴"),
    (15, "15-05", ["限购"], "缺限购机制"),
    (16, "16-01", ["安检"], "缺安检/电池等一票否决项"),
    (16, "16-04", ["风险"], "缺风险应对表"),
    (17, "17-04", ["回填"], "缺回填承诺表（不填=下个项目重复犯错）"),
    (18, "18-03", ["PART"], "缺执行包三段结构"),
]


def check_probes(ch, rep):
    miss = []
    for cno, fid, kws, hint in PROBES:
        blk = ch.get(cno, "")
        if not blk:
            continue
        if not any(k in blk for k in kws):
            miss.append((fid, hint))
    if miss:
        for fid, hint in miss:
            rep.warn(f"P {fid}", f"字段未检出：{hint}", "确认是否有等价表述；确实没有则补上")
    else:
        rep.info("P 探针", f"{len(PROBES)} 个关键字段全部检出")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="CMIS 方案自检器")
    ap.add_argument("path", help="方案 markdown 文件路径")
    ap.add_argument("--verbose", "-v", action="store_true", help="显示 INFO 级明细")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(f"文件不存在：{args.path}")
        return 2
    text = load(args.path)

    mode = "全案"
    m = re.search(r"交付模式[：:]\s*\*{0,2}(全案|标准案|精简案|急救案)", text)
    if m:
        mode = m.group(1)
    else:
        for cand in ("急救案", "精简案", "标准案"):
            if cand in text[:3000]:
                mode = cand
                break

    ch, order = chapters(text)
    rep = Report()

    print("=" * 64)
    print(f"CMIS 自检  ·  {os.path.basename(args.path)}")
    print(f"交付模式：{mode}    识别到章节：{len(order)} 个")
    print("=" * 64)

    if not order:
        # 未采用「第 N 章」结构：多为 v5.4 之前的历史归档，降级为提示，不做结构断言
        rep.warn("S00 非标准结构", "全文未识别到「第 N 章」标题，按历史格式处理，跳过结构类校验",
                 "新方案必须按 references/templates.md 的 18 章骨架输出；历史文件仅作归档")
        check_words(text, rep)
        rep.dump(args.verbose)
        print("\n结论：结构不达标（历史格式）。新交付物请按 templates.md 重排后再跑一次。")
        return 0

    check_structure(text, ch, order, mode, rep)
    check_basis_sections(ch, rep)
    check_d_refs(text, rep)
    check_aesthetic(ch, rep)
    rows = gate_b(ch, rep)
    qty_total, rev_total, gp_total = check_gate_b(rows, rep) if rows else (0, 0, 0)
    check_quant(ch, rows, qty_total, rep)
    check_headline(ch, rows, rev_total, gp_total, rep)
    check_leak(ch, rep)
    check_words(text, rep)
    check_appendix(ch, rep)
    check_probes(ch, rep)

    rep.dump(args.verbose)
    c = rep.counts()
    print()
    if c["FAIL"]:
        print("结论：不通过。FAIL 必须修完再交付（字段总账 §19 的一致性矩阵是硬约束）。")
        return 1
    print("结论：通过（0 FAIL）。WARN 请逐条确认，机械层保证不漏，人工层保证不假。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
