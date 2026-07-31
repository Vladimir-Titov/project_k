import logging
import re

from app.core.config import LogConfig
from app.core.config.logging import setup_logging


def raise_runtime_error() -> None:
    raise RuntimeError('boom')


def test_logging_uses_utc_stdout_format_without_duplicates(capsys: object) -> None:
    setup_logging(LogConfig(_env_file=None, level='INFO'))
    logger = logging.getLogger('app.test')

    logger.info('test message')

    output = capsys.readouterr().out
    pattern = (
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z'
        r' \| INFO \| app\.test:\d+ \| test message\n$'
    )
    assert re.match(pattern, output)
    assert output.count('test message') == 1


def test_logging_includes_exception_traceback(capsys: object) -> None:
    setup_logging(LogConfig(_env_file=None, level='INFO'))
    logger = logging.getLogger('app.test')

    try:
        raise_runtime_error()
    except RuntimeError:
        logger.exception('request failed')

    output = capsys.readouterr().out
    assert 'request failed' in output
    assert 'Traceback (most recent call last):' in output
    assert 'RuntimeError: boom' in output
