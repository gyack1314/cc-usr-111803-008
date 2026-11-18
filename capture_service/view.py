"""按本项目约定展示已接收资料与明确缺口。"""
from .ledger import entities
from .domain import assess
from .collection import coverage
from .trades import records as trade_records, current as current_trades
from .inventory import lots as inventory_lots

def overview(c,collection):
    rows=entities(c,collection)
    result=assess(rows)
    result['collection']=collection
    result['records']=[{'type':r['type'],'id':r['id'],'version':r['version'],'source_sha256':r['source']} for r in rows]
    result['coverage']=coverage(c,collection)
    result['transactions']=trade_records(c,collection)
    result['current_transactions']=current_trades(c,collection)
    result['inventory']=inventory_lots(c,collection)
    result['pending']={'missing_required':result['coverage']['missing_required'],
                       'revision_pending':result['coverage']['revision_pending'],
                       'unresolved_retractions':[item['transaction_id']
                                                 for item in result['unresolved_retractions']]}
    return result
