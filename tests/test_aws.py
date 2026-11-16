import io
import json
import unittest

from patchproof.aws_storage import AWSStore
from patchproof.capsule import seal
from patchproof.storage import StoreError
from test_capsule import example


class AWSError(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}


class S3:
    def __init__(self):
        self.files = {}

    def put_object(self, **kwargs):
        assert kwargs['IfNoneMatch'] == '*'
        key = kwargs['Key']
        if key in self.files:
            raise AWSError('PreconditionFailed')
        self.files[key] = kwargs['Body']

    def get_object(self, **kwargs):
        if kwargs['Key'] not in self.files:
            raise AWSError('NoSuchKey')
        return {'Body': io.BytesIO(self.files[kwargs['Key']])}


class Dynamo:
    def __init__(self):
        self.items = {}
        self.fail = False

    def put_item(self, **kwargs):
        if self.fail:
            raise AWSError('ProvisionedThroughputExceededException')
        self.items[kwargs['Item']['sk']['S']] = kwargs['Item']

    def query(self, **kwargs):
        return {'Items': list(reversed(list(self.items.values())))[:kwargs['Limit']]}


class AWSAdapterTests(unittest.TestCase):
    def test_partial_index_failure_can_be_repaired_idempotently(self):
        s3, dynamo = S3(), Dynamo()
        store = AWSStore(s3, dynamo, 'bucket', 'table')
        report = seal(example())
        dynamo.fail = True
        with self.assertRaises(StoreError):
            store.put(report)
        self.assertEqual(store.get(report['sha256']), report)
        dynamo.fail = False
        self.assertFalse(store.put(report))
        self.assertEqual(store.list()[0]['id'], report['sha256'])

    def test_s3_corruption_never_becomes_a_verified_report(self):
        s3, dynamo = S3(), Dynamo()
        store = AWSStore(s3, dynamo, 'bucket', 'table')
        report = seal(example()); store.put(report)
        s3.files['capsules/' + report['sha256'] + '.json'] = b'{}'
        with self.assertRaises(StoreError):
            store.get(report['sha256'])
        with self.assertRaises(StoreError):
            store.put(report)


if __name__ == '__main__':
    unittest.main()
