import uvicorn

from app.application import create_app
from app.core.config import get_app_config, get_log_config

app = create_app()


def main() -> None:
    app_config = get_app_config()
    log_config = get_log_config()
    uvicorn.run(
        'app.main:app',
        host=app_config.host,
        port=app_config.port,
        workers=app_config.workers,
        access_log=log_config.access_log,
        log_config=None,
    )


if __name__ == '__main__':
    main()
