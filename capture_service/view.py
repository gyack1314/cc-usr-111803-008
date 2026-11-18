"""按本项目约定展示已接收资料与明确缺口。"""
from .ledger import entities
from .domain import assess
from .collection import coverage
from .trades import records as trade_records
from .inventory import lots as inventory_lots

def overview(c,collection):
    rows=entities(c,collection)
    result=assess(rows)
    result['collection']=collection
    result['records']=[{'type':r['type'],'id':r['id'],'version':r['version'],'source_sha256':r['source']} for r in rows]
    result['coverage']=coverage(c,collection)
    result['transactions']=trade_records(c,collection)
    result['inventory']=inventory_lots(c,collection)
    return result
