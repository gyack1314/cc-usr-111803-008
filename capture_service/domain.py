"""解析来源身份及本项目公开资料字段。"""
import json
import re
from pathlib import Path
CONTRACT=json.loads((Path(__file__).resolve().parents[1]/'docs'/'source-contract.json').read_text(encoding='utf-8'))
def decode(raw,receipt):
    doc=json.loads(raw.decode('utf-8'))
    if not all(k in doc for k in ('kind','id','revision')): raise ValueError('资料身份缺失')
    kind=doc['kind']
    if kind not in CONTRACT['roles']: raise ValueError('未知来源类型')
    if any(k not in doc for k in CONTRACT['required_fields'][kind]): raise ValueError('来源业务字段缺失')
    return [{'type':kind,'id':doc['id'],'version':doc['revision'],'payload':{k:v for k,v in doc.items() if k not in ('kind','id','revision')}}]
def version_key(version):
    """来源版次按数字段比较，避免 v10 排在 v2 之前。"""
    return tuple((0,int(part)) if part.isdigit() else (1,part)
                 for part in re.split(r'(\d+)',str(version)))
def latest(rows):
    """每个来源身份（类型+id）只保留最高版次，作为当前流向依据；旧版仍留在账本供历史视图。"""
    chosen={}
    for row in rows:
        key=(row['type'],row['id'])
        if key not in chosen or version_key(row['version'])>version_key(chosen[key]['version']):
            chosen[key]=row
    return list(chosen.values())
def assess(rows):
    """按当前三来源契约核对候选关联；交易撤回按 transaction_id 核对并保留待核证据。"""
    current=latest(rows)
    left=sorted((r for r in current if r['type']==CONTRACT['roles'][0]),key=lambda r:version_key(r['version']))
    right=sorted((r for r in current if r['type']==CONTRACT['roles'][1]),key=lambda r:version_key(r['version']))
    pairs=[]
    for first in left:
        for second in right:
            a,b=first['payload'],second['payload']
            if a['lot']==b['lot'] and a['buyer']==b['seller'] and a['heads']>=b['heads']:
                pairs.append({'left_id':first['id'],'left_version':first['version'],
                              'right_id':second['id'],'right_version':second['version'],
                              'left_source':first['source'],'right_source':second['source']})
    known={}
    for row in current:
        if row['type'] in CONTRACT['roles'][:2]:
            known.setdefault(row['payload']['transaction_id'],row)
    retractions=[]
    for row in sorted((r for r in current if r['type']==CONTRACT['roles'][2]),
                      key=lambda r:(r['payload'].get('effective_on',''),r['id'])):
        payload=row['payload']
        target=known.get(payload['transaction_id'])
        resolved=target is not None and target['payload']['lot']==payload['lot']
        retractions.append({'id':row['id'],'version':row['version'],'source':row['source'],
                            'lot':payload['lot'],'transaction_id':payload['transaction_id'],
                            'heads':payload['heads'],'reason':payload.get('reason',''),
                            'effective_on':payload.get('effective_on',''),'resolved':resolved})
    return {'publishable':bool(pairs),'reasons':[] if pairs else ['转售批次与原买方及头数一致'],
            'received_types':sorted({r['type'] for r in rows}),
            'received_versions':len(rows),'matched_pairs':pairs,
            'retractions':retractions,
            'unresolved_retractions':[item for item in retractions if not item['resolved']],
            'candidate_relations':sorted({str(r['payload'].get(CONTRACT['relation_field'])) for r in rows})}
