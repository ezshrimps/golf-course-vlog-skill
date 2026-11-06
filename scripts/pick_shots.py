"""从 events.json 选出要做精细分析的真挥杆：sel_me.json（自己）和 sel_partner.json（球友）。"""
import json
import project as P

ev = json.load(open('events.json'))
for name, leg in (('me', P.ME), ('partner', P.PARTNER)):
    sel = [e for e in ev if e['leg'] == leg and e['hit']]
    json.dump(sel, open(f'sel_{name}.json', 'w'), indent=0)
    print(name, len(sel))
