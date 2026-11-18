"""计算每个批次仍留在育肥环节的头数。"""

from .trades import records


def lots(connection, collection):
    transactions = records(connection, collection)
    purchases = {}
    for item in transactions:
        if item['kind'] == 'auction_result':
            purchases[item['lot']] = {
                'lot': item['lot'],
                'heads_in': item['heads'],
                'holder': item['buyer'],
                'source_sha256': item['source_sha256'],
            }
    result = []
    for lot, purchase in sorted(purchases.items()):
        moved = sum(item['heads'] for item in transactions
                    if item['kind'] == 'resale_notice' and item['lot'] == lot)
        result.append({**purchase, 'heads_remaining': purchase['heads_in'] - moved})
    return result
