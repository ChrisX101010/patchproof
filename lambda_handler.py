"""AWS Lambda Function URL adapter. Import does not create cloud resources."""
import base64
import os

from patchproof.app import Application, response
from patchproof.aws_storage import AWSStore

_app = None


def handler(event, context):
    global _app
    if _app is None:
        import boto3
        _app = Application(AWSStore(boto3.client('s3'), boto3.client('dynamodb'),
                                   os.environ['REPORT_BUCKET'], os.environ['REPORT_TABLE']),
                           os.environ['PUBLISH_TOKEN'], mode='aws')
    try:
        body = event.get('body') or ''
        body = base64.b64decode(body, validate=True) if event.get('isBase64Encoded') else body.encode('utf-8')
        result = _app.handle(event['requestContext']['http']['method'], event.get('rawPath', '/'), event.get('headers'), body)
    except (ValueError, KeyError, UnicodeError):
        result = response(400, {'error': 'Invalid HTTP event'})
    return {'statusCode': result.status, 'headers': result.headers,
            'body': base64.b64encode(result.body).decode(), 'isBase64Encoded': True}
