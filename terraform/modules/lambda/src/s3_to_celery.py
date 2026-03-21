"""
Lambda function to transform S3 event notifications to Celery task format.

This function acts as a bridge between S3 and Celery:
1. S3 sends raw event notifications to this Lambda
2. Lambda transforms them into Celery task format
3. Lambda sends formatted tasks to SQS queue that Celery workers consume

Flow:
S3 Upload → Lambda (this function) → SQS (celery format) → Celery Worker
"""

import json
import boto3
import os
import uuid
import base64
from typing import Dict, Any, List

# Initialize SQS client
sqs = boto3.client('sqs')

# Get queue URL from environment variable
CELERY_QUEUE_URL = os.environ.get('CELERY_QUEUE_URL')

if not CELERY_QUEUE_URL:
    raise ValueError("CELERY_QUEUE_URL environment variable must be set")


def create_celery_message(s3_notification: str) -> tuple[str, Dict[str, Any]]:
    """
    Create a Celery-compatible SQS message from S3 notification.
    
    Returns:
        Tuple of (message_body, message_attributes)
    """
    task_id = str(uuid.uuid4())
    
    # Celery task payload
    task_payload = {
        "task": "sqs_consumer.process_s3_event",
        "id": task_id,
        "args": [s3_notification],
        "kwargs": {},
        "retries": 0,
        "eta": None,
        "expires": None,
        "utc": True,
        "callbacks": None,
        "errbacks": None,
        "chain": None,
        "chord": None
    }
    
    # Kombu message wrapper (what Celery expects)
    kombu_message = {
        "body": base64.b64encode(json.dumps(task_payload).encode()).decode(),
        "content-encoding": "utf-8",
        "content-type": "application/json",
        "headers": {},
        "properties": {
            "correlation_id": task_id,
            "reply_to": None,
            "delivery_mode": 2,
            "delivery_info": {
                "exchange": "",
                "routing_key": "s3-events"
            },
            "priority": 0,
            "body_encoding": "base64",
            "delivery_tag": str(uuid.uuid4())
        }
    }
    
    message_body = json.dumps(kombu_message)
    
    # SQS Message Attributes
    message_attributes = {
        "task": {
            "StringValue": "sqs_consumer.process_s3_event",
            "DataType": "String"
        },
        "id": {
            "StringValue": task_id,
            "DataType": "String"
        },
        "content-type": {
            "StringValue": "application/json",
            "DataType": "String"
        },
        "content-encoding": {
            "StringValue": "utf-8",
            "DataType": "String"
        }
    }
    
    return message_body, message_attributes


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for S3 event transformation.
    
    Args:
        event: S3 event notification from AWS
        context: Lambda context object
        
    Returns:
        Response dictionary with status and details
    """
    print(f"Received S3 event with {len(event.get('Records', []))} record(s)")
    
    processed = 0
    failed = 0
    results = []
    
    try:
        for record in event.get('Records', []):
            try:
                # Extract S3 information
                event_name = record.get('eventName', '')
                s3_info = record.get('s3', {})
                bucket_name = s3_info.get('bucket', {}).get('name', '')
                object_key = s3_info.get('object', {}).get('key', '')
                object_size = s3_info.get('object', {}).get('size', 0)
                
                print(f"Processing: s3://{bucket_name}/{object_key} ({object_size} bytes)")
                
                # Wrap single record in Records array
                s3_notification = json.dumps({
                    'Records': [record]
                })
                
                # Create Celery-compatible message
                message_body, message_attributes = create_celery_message(s3_notification)
                
                # Send to SQS
                response = sqs.send_message(
                    QueueUrl=CELERY_QUEUE_URL,
                    MessageBody=message_body,
                    MessageAttributes=message_attributes
                )
                
                task_id = message_attributes['id']['StringValue']
                
                print(f"✓ Sent Celery task {task_id} to SQS: {response['MessageId']}")
                print(f"  Event: {event_name}")
                print(f"  Object: s3://{bucket_name}/{object_key}")
                
                processed += 1
                results.append({
                    'status': 'success',
                    'task_id': task_id,
                    'sqs_message_id': response['MessageId'],
                    'bucket': bucket_name,
                    'key': object_key,
                    'size': object_size
                })
                
            except Exception as e:
                failed += 1
                error_msg = f"Failed to process record: {str(e)}"
                print(f"✗ {error_msg}")
                
                results.append({
                    'status': 'error',
                    'error': error_msg,
                    'record': record
                })
        
        # Summary
        print("=" * 80)
        print(f"Transformation complete: {processed} succeeded, {failed} failed")
        print("=" * 80)
        
        return {
            'statusCode': 200 if failed == 0 else 207,
            'body': json.dumps({
                'message': f'Processed {processed} S3 events',
                'processed': processed,
                'failed': failed,
                'results': results
            })
        }
        
    except Exception as e:
        error_msg = f"Critical error in Lambda handler: {str(e)}"
        print(f"✗ {error_msg}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'processed': processed,
                'failed': failed
            })
        }