import re
from collections import Counter

BASE = "/Users/faronpan/Agent/stockyidong_project"
txt = open(f"{BASE}/src/stockyidong_20260908_080337.txt", encoding="utf-8").read()

def parse(sec):
    m = re.search(r'【'+re.escape(sec)+r'标签页】\n(.*?)(?=\n共 \d+ 只)', txt, re.S)
    return {c: n.strip().lstrip('、') for n, c in re.findall(r'、?([^()]+?)\((\d{6})\)', m.group(1))}

lt = dict(parse('龙头股')); ths = dict(parse('同花顺')); m15 = parse('15Min')
ltN, thsN = len(lt), len(ths)

# code -> sector (stable keys)
SEC = {
 '300308':'算力/AI','002371':'半导体','603986':'半导体','301095':'半导体','688825':'半导体',
 '688300':'电子材料','601208':'电子材料','300936':'电子材料','688652':'半导体','688209':'半导体',
 '688678':'电子元件','301013':'电子元件','300709':'消费电子','300476':'PCB','600183':'PCB',
 '600703':'半导体','000636':'被动元件','603629':'消费电子','603890':'消费电子','301591':'新材料',
 '688629':'连接器','300602':'电子元件','300252':'通信','300378':'软件','002837':'算力/AI',
 '000977':'算力/AI','000938':'算力/AI','002396':'通信','300454':'软件','300170':'软件',
 '688095':'软件','003005':'软件','002354':'传媒/AI','002104':'金融科技','003040':'金融科技',
 '688836':'机器人','600487':'通信','601869':'通信','002491':'通信','603618':'线缆',
 '002300':'线缆','600869':'线缆','600667':'半导体封测','600967':'军工','601606':'军工',
 '002297':'军工','002265':'军工','300489':'半导体','600654':'安防','002155':'黄金/有色',
 '601212':'黄金/有色','601020':'黄金/有色','000426':'黄金/有色','002842':'小金属','600714':'小金属',
 '600367':'小金属','002428':'小金属','002716':'黄金/有色','600172':'新材料','600371':'农业',
 '600127':'农业','600540':'农业','600354':'农业','300189':'农业','002942':'农业',
 '600227':'化工','002407':'化工','600160':'化工','002165':'化工','002909':'化工',
 '300057':'新材料','600176':'玻纤','605006':'玻纤','600103':'造纸','002632':'新材料',
 '002886':'新材料','002580':'储能','001258':'新能源','002639':'氢能','600378':'化工',
 '002418':'新能源','000890':'金属制品','600353':'电子陶瓷','600479':'医药','600721':'医药',
 '600613':'医药','002412':'医药','002437':'医药','600664':'医药','002432':'医药',
 '688202':'医药','605179':'消费','601566':'消费','601086':'零售','600828':'零售',
 '603221':'家居','002084':'家居','603269':'环保','600519':'白酒','600186':'消费',
 '600162':'地产','000560':'地产','002081':'装修','000017':'零售','603958':'消费',
 '600892':'传媒','000892':'传媒','300413':'传媒','605577':'传媒','002059':'旅游',
 '301127':'环保','920895':'农机','000712':'金融','000567':'金融','600589':'算力/AI',
 '600121':'煤炭','600403':'煤炭','002328':'汽车零件','002536':'汽车零件','002131':'营销',
 '003032':'教育','002855':'消费电子','600722':'化工','002742':'其他',
}

univ = {}
for d in (lt, ths): univ.update(d)

# sector heat over full universe (160 slots)
heat = Counter()
for c in univ:
    heat[SEC.get(c, '其他')] += 1

# resonance: in BOTH lt & ths (15Min empty)
reso = [c for c in lt if c in ths]
maxh = max(heat.values()) if heat else 1
scored = []
for c in reso:
    s = SEC.get(c, '其他')
    score = round(200 + (heat[s] / maxh) * 40, 1)
    scored.append((score, c, univ[c], s, heat[s]))
scored.sort(reverse=True)

# Diversified Top5: top-scoring resonance stock from each of the 5 hottest sectors
sector_rank = [s for s, _ in heat.most_common()]
top5 = []
seen_sec = set()
for sc, c, n, s, h in scored:
    if s in seen_sec:
        continue
    top5.append({'code': c, 'name': n, 'sector': s, 'heat': h, 'score': sc})
    seen_sec.add(s)
    if len(top5) == 5:
        break

print(f"持仓概况: 龙头股{ltN}只 / 15Min{len(m15)}只 / 同花顺{thsN}只 | 共振(双榜){len(reso)}只")
print(f"板块热度(全样本{sum(heat.values())}票, {len(heat)}类):")
for s, n in heat.most_common():
    print(f"  {s:<10} {n}")
print("\n共振股 Top10 (共振权重 + 板块热度):")
for sc, c, n, s, h in scored[:10]:
    print(f"  {c} {n:<7} 板块={s:<9} 板块票={h} 评分={sc}")
print("\n未匹配板块的股票数:", sum(1 for c in univ if SEC.get(c) == '其他' or c not in SEC))

# diversified Top5 detail
sec_member = {}
for sc, c, n, s, h in scored:
    sec_member.setdefault(s, []).append((c, n))
print("\n=== 分散化 Top5 (各热门板块取共振最高分) ===")
for t in top5:
    members = sec_member[t['sector']]
    co = ', '.join(f"{nn}({cc})" for cc, nn in members)
    print(f"  {t['code']} {t['name']} | 板块={t['sector']}(票{t['heat']}) | 同板块共振:{co}")

import json
out = {
 'ltN': ltN, 'm15N': len(m15), 'thsN': thsN, 'resoN': len(reso),
 'heat': dict(heat),
 'top5': top5,
 'top_raw': [{'code': c, 'name': n, 'sector': s, 'heat': h, 'score': sc} for sc, c, n, s, h in scored[:8]],
 'reso_all': [{'code': c, 'name': univ[c], 'sector': SEC.get(c,'其他')} for c in reso],
}
json.dump(out, open(f"{BASE}/src/_tmp_sidong_result.json", "w"), ensure_ascii=False, indent=2)
print("\n[OK] saved _tmp_sidong_result.json")
