"""成交更正进入当前流向：修订与撤回改变当前存栏，历史发布仍可复现。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from capture_service.ledger import connect, receive
from capture_service.collection import collect, coverage, progress
from capture_service.inventory import lots
from capture_service.trades import records, current, retractions
from capture_service.view import overview
from capture_service.archive import release, get

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = '111803-008'


class TransactionCorrection(unittest.TestCase):
    def test_revision_then_retraction_updates_current_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            c = connect(Path(directory) / 'collection.sqlite3')
            collect(c, COLLECTION, ROOT / 'data' / 'normal.json')
            self.assertEqual(lots(c, COLLECTION)[0]['heads_remaining'], 40)
            weekly = release(c, COLLECTION)
            collect(c, COLLECTION, ROOT / 'data' / 'revised.json')
            lot = lots(c, COLLECTION)[0]
            self.assertEqual(lot['heads_in'], 90)
            self.assertEqual(lot['revision'], 'v2')
            self.assertEqual(lot['heads_remaining'], 10)
            collect(c, COLLECTION, ROOT / 'data' / 'event-pending.json')
            lot = lots(c, COLLECTION)[0]
            self.assertTrue(lot['pending'])
            self.assertEqual(coverage(c, COLLECTION)['missing_required'],
                             ['https://local-source-008.example.test/records/transaction_retraction-A'])
            collect(c, COLLECTION, ROOT / 'data' / 'event-complete.json')
            lot = lots(c, COLLECTION)[0]
            self.assertEqual(lot['resold_effective'], 60)
            self.assertEqual(lot['retracted'], 20)
            self.assertEqual(lot['heads_remaining'], 30)
            self.assertEqual(lot['pending'], [])
            resale = lot['resales'][0]
            self.assertEqual((resale['transaction_id'], resale['seller']), ('SALE-1', '育肥场甲'))
            self.assertEqual((resale['heads'], resale['retracted'], resale['effective_heads']), (80, 20, 60))
            basis = retractions(c, COLLECTION)
            self.assertEqual(len(basis), 1)
            self.assertEqual((basis[0]['transaction_id'], basis[0]['heads'], basis[0]['resolved']),
                             ('SALE-1', 20, True))
            flow = {item['transaction_id']: item for item in current(c, COLLECTION)}
            self.assertEqual(flow['BUY-1']['effective_heads'], 90)
            self.assertEqual(flow['BUY-1']['revision'], 'v2')
            self.assertEqual(flow['SALE-1']['effective_heads'], 60)
            self.assertEqual([item['transaction_id'] for item in records(c, COLLECTION)],
                             ['BUY-1', 'BUY-1', 'SALE-1'])
            frozen = get(c, COLLECTION, weekly)
            self.assertEqual(frozen['inventory'][0]['heads_remaining'], 40)
            self.assertEqual(frozen['inventory'][0]['heads_in'], 120)
            c.close()

    def test_retraction_is_not_a_new_trade_and_keeps_other_sales(self):
        with tempfile.TemporaryDirectory() as directory:
            c = connect(Path(directory) / 'collection.sqlite3')
            collect(c, COLLECTION, ROOT / 'data' / 'normal.json')
            collect(c, COLLECTION, ROOT / 'data' / 'event-complete.json')
            kinds = [item['kind'] for item in records(c, COLLECTION)]
            self.assertEqual(kinds, ['auction_result', 'resale_notice'])
            self.assertEqual([item['transaction_id'] for item in records(c, COLLECTION)],
                             ['BUY-1', 'SALE-1'])
            lot = lots(c, COLLECTION)[0]
            self.assertEqual(lot['heads_remaining'], 120 - 60)
            self.assertEqual(len(lot['resales']), 1)
            c.close()

    def test_unresolved_retraction_stays_pending_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            c = connect(Path(directory) / 'collection.sqlite3')
            collect(c, COLLECTION, ROOT / 'data' / 'normal.json')
            raw = json.dumps({'kind': 'transaction_retraction', 'id': 'transaction_retraction-X',
                              'revision': 'v1', 'lot': 'P-7', 'transaction_id': 'SALE-9',
                              'effective_on': '2026-11-16', 'heads': 20,
                              'reason': '成交数量更正'}, ensure_ascii=False).encode('utf-8')
            receipt = {'status': 200, 'body_sha256': hashlib.sha256(raw).hexdigest(),
                       'url': 'https://local-source-008.example.test/records/transaction_retraction-X'}
            receive(c, COLLECTION, raw, receipt)
            view = overview(c, COLLECTION)
            lot = view['inventory'][0]
            self.assertEqual(lot['heads_remaining'], 40)
            self.assertTrue(any('SALE-9' in reason for reason in lot['pending']))
            self.assertEqual(view['pending']['unresolved_retractions'], ['SALE-9'])
            self.assertEqual(view['unresolved_retractions'][0]['heads'], 20)
            c.close()

    def test_restart_after_interruption_does_not_double_count(self):
        from capture_service.transport import Replay
        from capture_service.ledger import entities
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'collection.sqlite3'
            c = connect(path)
            collect(c, COLLECTION, ROOT / 'data' / 'normal.json')
            collect(c, COLLECTION, ROOT / 'data' / 'revised.json')
            # 模拟中断：原文已写入账本，但接收进度尚未记录
            replay = Replay(ROOT / 'data' / 'event-complete.json')
            step = replay.steps[0]['request']
            raw, receipt = replay.request(step['method'], step['url'])
            receive(c, COLLECTION, raw, receipt)
            c.close()
            c = connect(path)
            self.assertEqual(len(entities(c, COLLECTION)), 4)
            self.assertEqual(len(progress(c, COLLECTION)), 3)
            collect(c, COLLECTION, ROOT / 'data' / 'event-complete.json')
            self.assertEqual(len(progress(c, COLLECTION)), 4)
            lot = lots(c, COLLECTION)[0]
            self.assertEqual(lot['resold_effective'], 60)
            self.assertEqual(lot['heads_remaining'], 30)
            # 再次重启接续同一批清单，头数不重复增加
            c.close()
            c = connect(path)
            collect(c, COLLECTION, ROOT / 'data' / 'normal.json')
            collect(c, COLLECTION, ROOT / 'data' / 'revised.json')
            collect(c, COLLECTION, ROOT / 'data' / 'event-complete.json')
            lot = lots(c, COLLECTION)[0]
            self.assertEqual(lot['heads_remaining'], 30)
            self.assertEqual(lot['retracted'], 20)
            self.assertEqual(len(progress(c, COLLECTION)), 4)
            c.close()


if __name__ == '__main__':
    unittest.main()
