"""计算每个批次仍留在育肥环节的头数。"""

from .trades import current as current_trades, retractions as retraction_records
from .collection import pending_requirements


def lots(connection, collection):
    transactions = current_trades(connection, collection)
    withdrawals = retraction_records(connection, collection)
    known = {item['transaction_id'] for item in transactions}
    purchases = {}
    for item in transactions:
        if item['kind'] == 'auction_result':
            purchases[item['lot']] = {
                'lot': item['lot'],
                'heads_in': item['effective_heads'],
                'holder': item['buyer'],
                'purchase_transaction_id': item['transaction_id'],
                'revision': item['revision'],
                'source_sha256': item['source_sha256'],
            }
    source_pending = ['%s：%s' % (entry['reason'], entry['url'])
                      for entry in pending_requirements(connection, collection)]
    result = []
    for lot, purchase in sorted(purchases.items()):
        resales = [item for item in transactions
                   if item['kind'] == 'resale_notice' and item['lot'] == lot]
        moved = sum(item['effective_heads'] for item in resales)
        retracted = sum(item['retracted'] for item in resales)
        pending = list(source_pending)
        for entry in withdrawals:
            if entry['lot'] == lot and entry['transaction_id'] not in known:
                pending.append('撤回指向未接收交易：%s' % entry['transaction_id'])
        for item in resales:
            if item['retracted'] > item['heads']:
                pending.append('撤回头数超出原交易：%s' % item['transaction_id'])
        result.append({**purchase,
                       'resales': [{'transaction_id': item['transaction_id'],
                                    'seller': item['seller'],
                                    'buyer': item['buyer'],
                                    'buyer_type': item['buyer_type'],
                                    'heads': item['heads'],
                                    'retracted': item['retracted'],
                                    'effective_heads': item['effective_heads'],
                                    'revision': item['revision'],
                                    'source_sha256': item['source_sha256']}
                                   for item in resales],
                       'resold_effective': moved,
                       'retracted': retracted,
                       'heads_remaining': purchase['heads_in'] - moved,
                       'pending': pending})
    return result
