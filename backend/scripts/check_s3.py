#!/usr/bin/env python
import json
import os
import sys
import argparse

try:
    from dotenv import load_dotenv
except Exception:
    print(json.dumps({"ok": False, "error": "python-dotenv not installed"}, ensure_ascii=False))
    sys.exit(1)

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:
    print(json.dumps({"ok": False, "error": "boto3 not installed"}, ensure_ascii=False))
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Check S3 bucket existence and permissions. Optionally list objects by prefix.")
    parser.add_argument("--prefix", default=None, help="Optional S3 prefix to list (e.g., 'WJ_MS_SERVICE/').")
    parser.add_argument("--max-keys", type=int, default=10, help="Max number of objects to list for the given prefix.")
    args = parser.parse_args()

    # Load env from backend/.env relative to this script
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(env_path)

    bucket = os.getenv('AWS_S3_BUCKET')
    region = os.getenv('AWS_REGION', 'ap-northeast-2')
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

    result = {
        'bucket': bucket,
        'region': region,
        'exists': None,
        'list_permission': None,
        'head_error': None,
        'list_error': None,
        'using_instance_role': bool(not access_key and not secret_key),
        'prefix': args.prefix,
        'prefix_count': None,
        'sample_keys': None,
    }

    try:
        s3 = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
    except Exception as e:
        result['exists'] = False
        result['head_error'] = f'Failed to create s3 client: {e}'
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    # Check bucket existence
    try:
        s3.head_bucket(Bucket=bucket)
        result['exists'] = True
    except ClientError as e:
        result['exists'] = False
        result['head_error'] = str(e)
    except Exception as e:
        result['exists'] = False
        result['head_error'] = str(e)

    # Check list permission
    try:
        s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        result['list_permission'] = True
    except Exception as e:
        result['list_permission'] = False
        result['list_error'] = str(e)

    # Optionally list objects under a prefix
    if result['list_permission'] and args.prefix:
        try:
            resp = s3.list_objects_v2(Bucket=bucket, Prefix=args.prefix, MaxKeys=args.max_keys)
            contents = resp.get('Contents', [])
            result['prefix_count'] = resp.get('KeyCount', len(contents))
            result['sample_keys'] = [c['Key'] for c in contents[:args.max_keys]] if contents else []
        except Exception as e:
            # Do not fail the entire script for prefix listing issues
            result['prefix_count'] = 0
            result['sample_keys'] = []
            # Attach error info in list_error if not already present
            if not result.get('list_error'):
                result['list_error'] = f'Prefix list error: {e}'

    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
