import json
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber
from fastapi import FastAPI

from app.core.config.storage import StorageConfig
from app.core.files.repository import FileStorageError
from app.core.files.s3 import S3FileRepository
from app.lifespans.storage import create_storage_lifespan


@pytest.fixture
def repository():
    files = S3FileRepository(StorageConfig(_env_file=None))
    yield files
    files.client.close()


@pytest.mark.asyncio
async def test_put_get_delete_and_public_url(repository) -> None:
    data = b'image bytes'
    stream = BytesIO(data)
    body = StreamingBody(stream, len(data))
    with Stubber(repository.client) as stub:
        stub.add_response(
            'put_object',
            {},
            {
                'Bucket': 'project-k',
                'Key': 'images/test.png',
                'Body': data,
                'ContentType': 'image/png',
            },
        )
        stub.add_response('get_object', {'Body': body}, {'Bucket': 'project-k', 'Key': 'images/test.png'})
        stub.add_response('delete_object', {}, {'Bucket': 'project-k', 'Key': 'images/test.png'})
        await repository.put('images/test.png', data, 'image/png')
        assert await repository.get('images/test.png') == data
        assert stream.closed
        await repository.delete('images/test.png')
        stub.assert_no_pending_responses()
    assert repository.public_url('images/some name.png') == 'http://127.0.0.1:9000/project-k/images/some%20name.png'


@pytest.mark.asyncio
@pytest.mark.parametrize('existing', [False, True])
async def test_local_bootstrap_creates_missing_bucket_and_only_allows_image_reads(repository, existing) -> None:
    policy = {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Effect': 'Allow',
                'Principal': '*',
                'Action': ['s3:GetObject'],
                'Resource': ['arn:aws:s3:::project-k/images/*'],
            }
        ],
    }
    with Stubber(repository.client) as stub:
        if existing:
            stub.add_response('head_bucket', {}, {'Bucket': 'project-k'})
        else:
            stub.add_client_error('head_bucket', '404', http_status_code=404, expected_params={'Bucket': 'project-k'})
            stub.add_response('create_bucket', {}, {'Bucket': 'project-k'})
        stub.add_response('put_bucket_policy', {}, {'Bucket': 'project-k', 'Policy': json.dumps(policy)})
        await repository.initialize_local_bucket()
        stub.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_bootstrap_does_not_treat_access_denied_as_missing_bucket(repository) -> None:
    with Stubber(repository.client) as stub:
        stub.add_client_error('head_bucket', '403', http_status_code=403, expected_params={'Bucket': 'project-k'})
        with pytest.raises(ClientError):
            await repository.initialize_local_bucket()
        stub.assert_no_pending_responses()


@pytest.mark.asyncio
async def test_upload_storage_failure_uses_repository_error(repository) -> None:
    with Stubber(repository.client) as stub:
        stub.add_client_error('put_object', 'AccessDenied', http_status_code=403)
        with pytest.raises(FileStorageError, match='unavailable'):
            await repository.put('images/test.png', b'image bytes', 'image/png')


@pytest.mark.asyncio
@pytest.mark.parametrize('initialize', [False, True])
async def test_storage_lifespan_exposes_and_closes_repository(repository, initialize) -> None:
    repository.config.initialize_local_bucket = initialize
    repository.initialize_local_bucket = AsyncMock()
    repository.close = AsyncMock()
    app = FastAPI()
    async with create_storage_lifespan(repository)(app):
        assert app.state.files is repository
        assert repository.initialize_local_bucket.await_count == int(initialize)
    repository.close.assert_awaited_once()
    assert not hasattr(app.state, 'files')


@pytest.mark.asyncio
async def test_storage_client_is_closed_if_initialization_fails(repository) -> None:
    repository.config.initialize_local_bucket = True
    repository.initialize_local_bucket = AsyncMock(side_effect=RuntimeError('unavailable'))
    repository.close = AsyncMock()
    app = FastAPI()
    with pytest.raises(RuntimeError, match='unavailable'):
        async with create_storage_lifespan(repository)(app):
            pytest.fail('Startup must fail')
    repository.close.assert_awaited_once()
    assert not hasattr(app.state, 'files')
