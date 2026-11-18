"""按批次列出已接收的竞价成交和后续转售。"""

from .ledger import entities
from .domain import latest, version_key

TRADE_TYPES = ('auction_result', 'resale_notice')
RETRACTION_TYPE = 'transaction_retraction'


def records(connection, collection):
    transactions = []
    for row in entities(connection, collection):
        if row['type'] not in TRADE_TYPES:
            continue
        payload = row['payload']
        transactions.append({
            'kind': row['type'],
            'lot': payload['lot'],
            'transaction_id': payload['transaction_id'],
            'effective_on': payload['effective_on'],
            'heads': payload['heads'],
            'seller': payload.get('seller'),
            'buyer': payload['buyer'],
            'buyer_type': payload.get('buyer_type', '育肥场'),
            'source_sha256': row['source'],
            'revision': row['version'],
        })
    return sorted(transactions, key=lambda item: (item['effective_on'], item['transaction_id']))


def current(connection, collection):
    """当前流向：每个交易身份取最新来源版次，并扣除指向该交易的已接收撤回头数。"""
    rows = entities(connection, collection)
    withdrawn = {}
    for row in latest([r for r in rows if r['type'] == RETRACTION_TYPE]):
        payload = row['payload']
        target = payload['transaction_id']
        withdrawn[target] = withdrawn.get(target, 0) + payload['heads']
    chosen = {}
    for row in latest([r for r in rows if r['type'] in TRADE_TYPES]):
        payload = row['payload']
        key = payload['transaction_id']
        prior = chosen.get(key)
        if prior is None or version_key(row['version']) > version_key(prior['version']):
            chosen[key] = row
    transactions = []
    for row in chosen.values():
        payload = row['payload']
        retracted = withdrawn.get(payload['transaction_id'], 0)
        transactions.append({
            'kind': row['type'],
            'lot': payload['lot'],
            'transaction_id': payload['transaction_id'],
            'effective_on': payload['effective_on'],
            'heads': payload['heads'],
            'retracted': retracted,
            'effective_heads': max(payload['heads'] - retracted, 0),
            'seller': payload.get('seller'),
            'buyer': payload['buyer'],
            'buyer_type': payload.get('buyer_type', '育肥场'),
            'source_sha256': row['source'],
            'revision': row['version'],
        })
    return sorted(transactions, key=lambda item: (item['effective_on'], item['transaction_id']))


def retractions(connection, collection):
    """撤回依据：指向原交易的更正记录及其核对状态；未核对的引用保留为待核。"""
    rows = entities(connection, collection)
    known = {row['payload']['transaction_id'] for row in rows if row['type'] in TRADE_TYPES}
    result = []
    for row in latest([r for r in rows if r['type'] == RETRACTION_TYPE]):
        payload = row['payload']
        result.append({
            'id': row['id'],
            'lot': payload['lot'],
            'transaction_id': payload['transaction_id'],
            'effective_on': payload['effective_on'],
            'heads': payload['heads'],
            'reason': payload.get('reason', ''),
            'resolved': payload['transaction_id'] in known,
            'source_sha256': row['source'],
            'revision': row['version'],
        })
    return sorted(result, key=lambda item: (item['effective_on'], item['id']))
