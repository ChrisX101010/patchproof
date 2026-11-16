"""A small, versioned evidence format. Integrity is not execution attestation."""
from datetime import datetime
import hashlib
import hmac
import json
import re
from urllib.parse import urlsplit

MAX_BYTES = 256 * 1024
MAX_INTEGER = 2**53 - 1
HEX = re.compile(r'^[a-f0-9]{64}$')


class CapsuleError(ValueError):
    pass


def require(value, message):
    if not value:
        raise CapsuleError(message)


def canonical(value):
    def check(item, depth=0):
        require(depth <= 32, 'JSON nesting too deep')
        if item is None or type(item) is bool:
            return
        if type(item) is int:
            require(0 <= item <= MAX_INTEGER, 'integer outside safe range')
        elif type(item) is str:
            try:
                item.encode('utf-8')
            except UnicodeError:
                raise CapsuleError('invalid Unicode string') from None
        elif type(item) is list:
            for child in item:
                check(child, depth + 1)
        elif type(item) is dict:
            for key, child in item.items():
                require(type(key) is str and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', key), 'non-ASCII or unsupported field name')
                check(child, depth + 1)
        else:
            raise CapsuleError('unsupported JSON type; floats are not supported')
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def shape(value, keys, label):
    require(type(value) is dict and set(value) == set(keys.split()), label + ': missing or unknown fields')


def text(value, label, maximum=5000):
    require(type(value) is str and 0 < len(value) <= maximum and value.strip() == value, label + ': invalid text')
    require(not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', value), label + ': control characters')
    return value


def integer(value, label):
    require(type(value) is int and 0 <= value <= MAX_INTEGER, label + ': expected nonnegative safe integer')


def link(value, label):
    text(value, label, 2048)
    try:
        parsed = urlsplit(value)
        require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password and
                parsed.port in (None, 443) and not re.search(r'\s', value), label + ': expected HTTPS URL')
    except ValueError as error:
        raise CapsuleError(label + ': invalid URL') from error


def validate(payload):
    shape(payload, 'schemaVersion title project repository pullRequest createdAt baseline candidate environment groups comparison limitations evidence', 'payload')
    require(type(payload['schemaVersion']) is int and payload['schemaVersion'] == 1, 'unsupported schema version')
    for name in ('title', 'project'):
        text(payload[name], name, 200)
    for name in ('repository', 'pullRequest'):
        link(payload[name], name)
    try:
        require(type(payload['createdAt']) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', payload['createdAt']), 'createdAt: expected exact UTC timestamp')
        datetime.strptime(payload['createdAt'], '%Y-%m-%dT%H:%M:%SZ')
    except (TypeError, ValueError):
        raise CapsuleError('createdAt: expected UTC timestamp') from None
    for name in ('baseline', 'candidate'):
        shape(payload[name], 'commit', name)
        require(type(payload[name]['commit']) is str and re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})', payload[name]['commit']), 'invalid commit')
    shape(payload['environment'], 'os toolchain runtime', 'environment')
    for key, value in payload['environment'].items():
        text(value, key, 200)
    groups = payload['groups']
    require(type(groups) is list and 1 <= len(groups) <= 128, 'groups: expected 1..128 entries')
    names = set()
    for group in groups:
        shape(group, 'name total passed failed skipped scope', 'group')
        text(group['name'], 'group name', 120)
        require(group['name'] not in names, 'duplicate group name')
        names.add(group['name'])
        text(group['scope'], 'scope')
        for key in ('total', 'passed', 'failed', 'skipped'):
            integer(group[key], key)
        require(group['total'] > 0 and group['total'] == group['passed'] + group['failed'] + group['skipped'], 'inconsistent test counts')
    comparison = payload['comparison']
    shape(comparison, 'name baseline candidate', 'comparison')
    text(comparison['name'], 'comparison name', 200)
    for name in ('baseline', 'candidate'):
        shape(comparison[name], 'total failed', 'comparison ' + name)
        for key in ('total', 'failed'):
            integer(comparison[name][key], key)
        require(0 < comparison[name]['total'] and comparison[name]['failed'] <= comparison[name]['total'], 'inconsistent runtime counts')
    limitations = payload['limitations']
    require(type(limitations) is list and 1 <= len(limitations) <= 32, 'limitations must be explicit')
    for item in limitations:
        text(item, 'limitation')
    evidence = payload['evidence']
    require(type(evidence) is list and 1 <= len(evidence) <= 1000, 'evidence: expected 1..1000 files')
    names = set()
    for item in evidence:
        shape(item, 'name sha256 bytes', 'evidence')
        name = item['name']
        require(type(name) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}', name) and '..' not in name, 'unsafe evidence filename')
        require(name not in names, 'duplicate evidence filename')
        names.add(name)
        require(type(item['sha256']) is str and HEX.fullmatch(item['sha256']), 'invalid evidence digest')
        integer(item['bytes'], 'bytes')
    require(len(canonical(payload)) < MAX_BYTES - 100, 'capsule exceeds size limit')


def seal(payload):
    validate(payload)
    # A roundtrip prevents the caller mutating our sealed payload by alias.
    raw = canonical(payload)
    return {'payload': json.loads(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def verify(envelope):
    shape(envelope, 'payload sha256', 'capsule')
    validate(envelope['payload'])
    require(type(envelope['sha256']) is str and HEX.fullmatch(envelope['sha256']), 'invalid capsule digest')
    actual = hashlib.sha256(canonical(envelope['payload'])).hexdigest()
    require(hmac.compare_digest(actual, envelope['sha256']), 'capsule digest mismatch')
    return actual


def load(raw):
    if isinstance(raw, str):
        try:
            raw = raw.encode('utf-8')
        except UnicodeError:
            raise CapsuleError('invalid UTF8') from None
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, 'capsule exceeds size limit')

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    try:
        envelope = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise CapsuleError('invalid capsule JSON: ' + str(error)[:120]) from None
    verify(envelope)
    return envelope


def verify_files(envelope, files):
    verify(envelope)
    return {item['name']: ('missing' if item['name'] not in files else
            'match' if len(files[item['name']]) == item['bytes'] and hashlib.sha256(files[item['name']]).hexdigest() == item['sha256'] else 'mismatch')
            for item in envelope['payload']['evidence']}
