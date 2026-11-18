"""按批次列出已接收的竞价成交和后续转售。"""

from .ledger import entities


def records(connection, collection):
    transactions = []
    for row in entities(connection, collection):
        if row['type'] not in ('auction_result', 'resale_notice'):
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
