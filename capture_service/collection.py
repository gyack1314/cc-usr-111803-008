"""按来源清单接收原文，持久保存待收范围与接收进度。"""
from .ledger import entities
from .domain import assess
import json
from pathlib import Path
from .transport import Replay
from .ledger import receive

def initialize(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS collection_sources (
      collection TEXT NOT NULL, source_url TEXT NOT NULL,
      source_kind TEXT NOT NULL, required INTEGER NOT NULL,
      expected_revision TEXT NOT NULL DEFAULT '',
      PRIMARY KEY(collection, source_url))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS collection_progress (
      collection TEXT NOT NULL, source_url TEXT NOT NULL,
      body_sha256 TEXT NOT NULL, received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(collection, source_url, body_sha256))""")
    connection.commit()

def register_sources(connection, collection, manifest_path):
    """来源目录保留尚未取得的项目；来源身份变动要先更新目录。"""
    initialize(connection)
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    sources = manifest.get('sources', [])
    with connection:
        for source in sources:
            connection.execute(
                'INSERT INTO collection_sources(collection,source_url,source_kind,required,expected_revision) '
                'VALUES(?,?,?,?,?) ON CONFLICT(collection,source_url) DO UPDATE SET '
                'source_kind=excluded.source_kind,required=excluded.required,expected_revision=excluded.expected_revision',
                (collection, source['url'], source['kind'], int(source.get('required', True)),
                 source.get('expected_revision', '')))

def collect(connection, collection, manifest_path):
    """按清单重放来源，重启后接续已经接收的相同字节。"""
    register_sources(connection, collection, manifest_path)
    replay = Replay(manifest_path)
    result = []
    for step in replay.steps:
        request = step['request']
        raw, receipt = replay.request(request['method'], request['url'])
        digest = receive(connection, collection, raw, receipt)
        with connection:
            connection.execute(
                'INSERT OR IGNORE INTO collection_progress(collection,source_url,body_sha256) VALUES(?,?,?)',
                (collection, receipt['url'], digest))
        result.append(dict(source_url=receipt['url'], body_sha256=digest))
    return result

def progress(connection, collection):
    initialize(connection)
    return [dict(source_url=row[0], body_sha256=row[1], received_at=row[2])
            for row in connection.execute(
                'SELECT source_url,body_sha256,received_at FROM collection_progress WHERE collection=? ORDER BY source_url',
                (collection,))]

def received_revisions(connection, collection, source_url):
    """某来源链接已接收并经账本核对的来源版次集合。"""
    initialize(connection)
    return {row[0] for row in connection.execute(
        'SELECT e.version FROM entities e JOIN receipts r '
        'ON r.collection=e.collection AND r.body_sha256=e.receipt_sha256 '
        'WHERE e.collection=? AND r.source_url=?', (collection, source_url))}

def pending_requirements(connection, collection):
    """目录要求但尚未核实的来源：未接收或版次不符；标记待核而不是按零头数处理。"""
    initialize(connection)
    pending = []
    rows = connection.execute(
        'SELECT source_url,source_kind,required,expected_revision FROM collection_sources '
        'WHERE collection=? ORDER BY source_url', (collection,)).fetchall()
    for url, kind, required, expected in rows:
        versions = received_revisions(connection, collection, url)
        if required and not versions:
            pending.append({'url': url, 'kind': kind, 'reason': '来源尚未接收'})
        elif expected and expected not in versions:
            pending.append({'url': url, 'kind': kind, 'reason': '来源版次待核',
                            'expected_revision': expected})
    return pending

def coverage(connection, collection):
    """区分来源接收进度与已核实的业务资料范围。"""
    initialize(connection)
    rows = connection.execute(
        'SELECT s.source_url,s.source_kind,s.required,s.expected_revision,COUNT(p.body_sha256) '
        'FROM collection_sources s LEFT JOIN collection_progress p '
        'ON p.collection=s.collection AND p.source_url=s.source_url '
        'WHERE s.collection=? GROUP BY s.source_url,s.source_kind,s.required,s.expected_revision ORDER BY s.source_url',
        (collection,)).fetchall()
    view = assess(entities(connection, collection))
    verified = {source for pair in view['matched_pairs']
                for source in (pair['left_source'], pair['right_source'])}
    verified |= {item['source'] for item in view['retractions'] if item['resolved']}
    sources = []
    for url, kind, required, expected, received in rows:
        revisions = received_revisions(connection, collection, url)
        sources.append(dict(url=url, kind=kind, required=bool(required),
                            expected_revision=expected,
                            received_versions=received,
                            revision_pending=bool(expected) and expected not in revisions,
                            verified=any(digest in verified for digest, in connection.execute(
                                'SELECT p.body_sha256 FROM collection_progress p JOIN receipts r '
                                'ON r.collection=p.collection AND r.body_sha256=p.body_sha256 '
                                'WHERE p.collection=? AND p.source_url=? AND r.source_url=p.source_url',
                                (collection, url)))))
    return {'expected': len(rows), 'received': sum(bool(row[4]) for row in rows),
            'missing_required': [row[0] for row in rows if row[2] and not row[4]],
            'revision_pending': [item['url'] for item in sources if item['revision_pending']],
            'unverified_required': [item['url'] for item in sources
                                    if item['required'] and not item['verified']],
            'sources': sources}
