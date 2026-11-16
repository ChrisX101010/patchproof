"""AWS persistence. Unit doubles are not a substitute for an actual cloud smoke test."""
import json

from .capsule import MAX_BYTES, canonical, load, verify
from .storage import StoreError, metadata


def code(error):
    return getattr(error, 'response', {}).get('Error', {}).get('Code', '')


class AWSStore:
    def __init__(self, s3, dynamo, bucket, table):
        self.s3, self.dynamo, self.bucket, self.table = s3, dynamo, bucket, table

    def get(self, identity):
        try:
            result = self.s3.get_object(Bucket=self.bucket, Key='capsules/' + identity + '.json')
            body = result['Body']
            try:
                report = load(body.read(MAX_BYTES + 1))
            finally:
                body.close()
            if report['sha256'] != identity:
                raise StoreError('Stored report identity differs')
            return report
        except Exception as error:
            if code(error) in ('NoSuchKey', '404'):
                return None
            raise StoreError('S3 evidence read failed') from error

    def put(self, report):
        identity = verify(report)
        created = True
        try:
            try:
                self.s3.put_object(Bucket=self.bucket, Key='capsules/' + identity + '.json',
                                   Body=canonical(report), ContentType='application/json', IfNoneMatch='*')
            except Exception as error:
                if code(error) not in ('PreconditionFailed', 'ConditionalRequestConflict', '412', '409'):
                    raise
                created = False
                if self.get(identity) != report:
                    raise StoreError('Existing content is missing or differs; retry publication')
            # Repeated publication repairs this entry if an earlier index write failed.
            self.dynamo.put_item(TableName=self.table, Item={
                'pk': {'S': 'REPORTS'}, 'sk': {'S': report['payload']['createdAt'] + '#' + identity},
                'document': {'S': json.dumps(metadata(report), separators=(',', ':'))}})
            return created
        except Exception as error:
            raise StoreError('Publication incomplete; retry with the identical capsule') from error

    def list(self):
        try:
            result = self.dynamo.query(TableName=self.table, KeyConditionExpression='#pk = :pk',
                                       ExpressionAttributeNames={'#pk': 'pk'},
                                       ExpressionAttributeValues={':pk': {'S': 'REPORTS'}},
                                       ScanIndexForward=False, Limit=25)
            return [json.loads(item['document']['S']) for item in result.get('Items', [])]
        except Exception as error:
            raise StoreError('Report index unavailable') from error
