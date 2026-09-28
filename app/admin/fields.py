from typing import Any

from starlette.requests import Request
from starlette_admin.fields import ImageField


class ImageUploadField(ImageField):
    async def parse_obj(self, request: Request, obj: Any) -> dict[str, str] | None:
        if obj.image_url:
            return {'url': obj.image_url}
        return None
