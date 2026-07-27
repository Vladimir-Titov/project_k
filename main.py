import uvicorn

from settings import get_app_config, get_log_config


def main() -> None:
    app_config = get_app_config()
    log_config = get_log_config()
    uvicorn.run(
        'web.create_app:app',
        host=app_config.host,
        port=app_config.port,
        workers=app_config.workers,
        access_log=log_config.access_log,
        log_config=None,
    )


if __name__ == '__main__':
    main()
