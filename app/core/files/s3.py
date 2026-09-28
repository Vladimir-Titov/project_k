import json
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from starlette.concurrency import run_in_threadpool

from app.core.config.storage import StorageConfig
from app.core.files.repository import FileStorageError


class S3FileRepository:
    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self.client = boto3.client(
            's3',
            endpoint_url=str(config.endpoint_url),
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key.get_secret_value(),
            region_name=config.region,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'},
                connect_timeout=5,
                read_timeout=30,
                retries={'mode': 'standard', 'max_attempts': 2},
            ),
        )

    async def initialize_local_bucket(self) -> None:
        """Explicit opt-in bootstrap for the local development bucket."""
        try:
            await run_in_threadpool(self.client.head_bucket, Bucket=self.config.bucket)
        except ClientError as error:
            if error.response['Error']['Code'] not in {'404', 'NoSuchBucket', 'NotFound'}:
                raise
            try:
                await run_in_threadpool(self.client.create_bucket, Bucket=self.config.bucket)
            except ClientError as create_error:
                if create_error.response['Error']['Code'] != 'BucketAlreadyOwnedByYou':
                    raise
        policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Principal': '*',
                    'Action': ['s3:GetObject'],
                    'Resource': [f'arn:aws:s3:::{self.config.bucket}/images/*'],
                }
            ],
        }
        await run_in_threadpool(self.client.put_bucket_policy, Bucket=self.config.bucket, Policy=json.dumps(policy))

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            await run_in_threadpool(
                self.client.put_object,
                Bucket=self.config.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as error:
            raise FileStorageError('Image storage is unavailable. Try again later.') from error

    async def get(self, key: str) -> bytes:
        def read() -> bytes:
            response = self.client.get_object(Bucket=self.config.bucket, Key=key)
            with response['Body'] as body:
                return body.read()

        return await run_in_threadpool(read)

    async def delete(self, key: str) -> None:
        await run_in_threadpool(self.client.delete_object, Bucket=self.config.bucket, Key=key)

    def public_url(self, key: str) -> str:
        return f'{str(self.config.public_url).rstrip("/")}/{quote(key, safe="/")}'

    async def close(self) -> None:
        await run_in_threadpool(self.client.close)
