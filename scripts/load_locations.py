"""Load authored locations and images. Run after migrations; safe to repeat."""

import asyncio
import hashlib
import json
import os
from itertools import pairwise
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
from uuid import uuid4

import asyncpg
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
LOCATION_COUNT = 13


def load_content():
    records = json.loads((ROOT / 'specifications/locations-content.json').read_text())
    assets = ROOT.parent / 'project_k_web/static'
    for record in records:
        image = assets / record['image_file']
        if not image.is_file() or not record['description'].strip():
            raise ValueError(f'Incomplete location: {record["code"]}')
    if len(records) != LOCATION_COUNT or len({r['code'] for r in records}) != LOCATION_COUNT:
        raise ValueError('Expected 13 unique locations')
    return records, assets


def roads():
    for world in ('teren', 'sairan'):
        zones = ['city', 'suburb', 'forest', 'quarry', 'ruins', 'gates']
        for first, second in pairwise(zones):
            a, b = f'loc-{world}-{first}', f'loc-{world}-{second}'
            yield a, b, True
            yield b, a, True
        # Keep gate links configured but disabled until entry conditions exist.
        yield f'loc-{world}-gates', 'loc-borderland', False
        yield 'loc-borderland', f'loc-{world}-gates', False


def upload_images(settings, records, assets):
    endpoint = settings.get('S3_ENDPOINT_URL', 'http://127.0.0.1:9000')
    bucket = settings.get('S3_BUCKET', 'project-k')
    public = settings.get('S3_PUBLIC_URL', f'{endpoint}/{bucket}').rstrip('/')
    client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=settings.get('S3_ACCESS_KEY', 'rustfsadmin'),
        aws_secret_access_key=settings.get('S3_SECRET_KEY', 'rustfsadmin'),
        region_name=settings.get('S3_REGION', 'us-east-1'),
        config=Config(connect_timeout=5, read_timeout=30, retries={'max_attempts': 2}),
    )
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response['Error']['Code'] not in {'404', 'NoSuchBucket'}:
            raise
        client.create_bucket(Bucket=bucket)
        # Apply only to a newly created bucket; never replace an existing policy.
        client.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(
                {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Principal': '*',
                            'Action': 's3:GetObject',
                            'Resource': f'arn:aws:s3:::{bucket}/images/*',
                        }
                    ],
                }
            ),
        )
    for record in records:
        data = (assets / record['image_file']).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        key = f'images/locations/{record["code"]}-{digest}.png'
        try:
            client.head_object(Bucket=bucket, Key=key)
        except ClientError as error:
            if error.response['Error']['Code'] not in {'404', 'NoSuchKey'}:
                raise
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType='image/png',
                CacheControl='public, max-age=31536000, immutable',
            )
        record['image_url'] = f'{public}/{quote(key, safe="/")}'
        # Check the exact unsigned URL that the frontend will receive, including bytes.
        with urlopen(record['image_url'], timeout=30) as response:
            if hashlib.sha256(response.read()).hexdigest() != digest:
                raise ValueError(f'Image verification failed: {record["code"]}')
        print(f'Image ready: {record["code"]}')


async def main():
    settings = {**dotenv_values(ROOT / '.env'), **os.environ}
    records, assets = load_content()
    connection = await asyncpg.connect(
        host=settings.get('DB_HOST', '127.0.0.1'),
        port=int(settings.get('DB_PORT', '40321')),
        database=settings.get('DB_DATABASE', 'postgres'),
        user=settings.get('DB_USER', 'postgres'),
        password=settings.get('DB_PASSWORD', 'postgres'),
        timeout=10,
    )
    try:
        if not await connection.fetchval("SELECT to_regclass('frontiers.locations')"):
            raise RuntimeError('Apply database migrations before loading locations')
        await asyncio.to_thread(upload_images, settings, records, assets)
        async with connection.transaction():
            ids = {}
            for record in records:
                ids[record['code']] = await connection.fetchval(
                    """
                    INSERT INTO frontiers.locations (id, code, title, description, image_url)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (code) DO UPDATE SET title=EXCLUDED.title,
                      description=EXCLUDED.description, image_url=EXCLUDED.image_url, updated_at=now()
                    RETURNING id
                """,
                    uuid4(),
                    record['code'],
                    record['title'],
                    record['description'],
                    record['image_url'],
                )
            for source, destination, enabled in roads():
                await connection.execute(
                    """
                    INSERT INTO frontiers.location_transitions
                      (id, from_location_id, to_location_id, base_duration_seconds, is_enabled)
                    VALUES ($1, $2, $3, 30, $4)
                    ON CONFLICT (from_location_id, to_location_id) DO NOTHING
                """,
                    uuid4(),
                    ids[source],
                    ids[destination],
                    enabled,
                )
            filled = await connection.fetchval(
                """
                SELECT count(*) FROM frontiers.locations WHERE code = ANY($1::text[])
                  AND description <> '' AND image_url <> ''
            """,
                list(ids),
            )
            if filled != len(records):
                raise RuntimeError('Location verification failed')
        print(f'Loaded {filled} complete locations. Existing road settings and IDs preserved.')
        print('Roads:', await connection.fetchval('SELECT count(*) FROM frontiers.location_transitions'))
    finally:
        await connection.close()


if __name__ == '__main__':
    asyncio.run(main())
