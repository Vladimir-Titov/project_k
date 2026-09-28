import os
from io import BytesIO
from uuid import uuid4

import httpx2
import pytest
from PIL import Image
from starlette.datastructures import UploadFile

from app.core.config.storage import StorageConfig
from app.core.files.images import ImageService
from app.core.files.s3 import S3FileRepository


@pytest.mark.skipif(
    os.getenv('RUN_S3_INTEGRATION') != '1',
    reason='Requires local RustFS: docker compose up -d --wait rustfs',
)
@pytest.mark.asyncio
async def test_real_rustfs_upload_public_read_private_access_and_delete() -> None:
    config = StorageConfig()
    files = S3FileRepository(config)
    image_key = None
    private_key = f'private/{uuid4().hex}.png'
    buffer = BytesIO()
    Image.new('RGB', (2, 2), 'blue').save(buffer, format='PNG')
    data = buffer.getvalue()
    try:
        await files.initialize_local_bucket()
        # A second initialization must also succeed with an existing bucket.
        await files.initialize_local_bucket()
        url = await ImageService(files, config.max_image_size_bytes).upload(
            UploadFile(BytesIO(data), filename='test.png'),
        )
        image_key = url.removeprefix(f'{str(config.public_url).rstrip("/")}/')
        assert await files.get(image_key) == data
        await files.put(private_key, data, 'image/png')
        async with httpx2.AsyncClient() as client:
            response = await client.get(url)
            assert response.status_code == 200
            assert response.content == data
            assert response.headers['content-type'] == 'image/png'
            assert (await client.get(files.public_url(private_key))).status_code == 403
            assert (await client.get(str(config.public_url), params={'list-type': '2'})).status_code == 403
            assert (await client.put(url, content=b'overwrite')).status_code == 403
            assert (await client.delete(url)).status_code == 403
        assert await files.get(image_key) == data
        await files.delete(image_key)
        async with httpx2.AsyncClient() as client:
            assert (await client.get(url)).status_code == 404
    finally:
        if image_key is not None:
            await files.delete(image_key)
        await files.delete(private_key)
        await files.close()
