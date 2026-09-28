from io import BytesIO
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.core.files.repository import FileRepository

IMAGE_FORMATS = {
    'PNG': ('png', 'image/png'),
    'JPEG': ('jpg', 'image/jpeg'),
    'WEBP': ('webp', 'image/webp'),
    'GIF': ('gif', 'image/gif'),
}
MAX_IMAGE_PIXELS = 16_000_000


class InvalidImageError(ValueError):
    pass


def inspect_image(data: bytes) -> tuple[str, str]:
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in IMAGE_FORMATS:
                raise InvalidImageError('Use PNG, JPEG, WebP or GIF images.')
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise InvalidImageError('Image must not exceed 16 megapixels.')
            result = IMAGE_FORMATS[image.format]
            image.verify()
            return result
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise InvalidImageError('The file is not a valid image.') from error


class ImageService:
    def __init__(self, files: FileRepository, max_size_bytes: int) -> None:
        self.files = files
        self.max_size_bytes = max_size_bytes

    async def upload(self, file: UploadFile) -> str:
        data = await file.read(self.max_size_bytes + 1)
        if len(data) > self.max_size_bytes:
            raise InvalidImageError(f'Image must not exceed {self.max_size_bytes // (1024 * 1024)} MB.')
        extension, content_type = await run_in_threadpool(inspect_image, data)
        key = f'images/{uuid4().hex}.{extension}'
        await self.files.put(key, data, content_type)
        return self.files.public_url(key)
