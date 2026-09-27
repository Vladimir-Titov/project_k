"""Враг для отладки боёв через API.

Запуск: python3 autobattle.py --login enemy
Нужен существующий аккаунт с персонажем; пароль запрашивается при запуске.
Начни бой с этим персонажем из своего аккаунта. Остановка: Ctrl+C.
Здоровье восстанавливается при запуске и после каждого боя. Отключение: --no-rest.
Последовательность: python3 autobattle.py --login enemy --actions attack heal attack
"""

# ruff: noqa: RUF001, RUF002

import argparse
import getpass
import json
import os
import random
import time
from http import HTTPStatus
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

MAX_DELAY = 30


class ApiError(Exception):
    def __init__(self, status, detail):
        super().__init__(f'HTTP {status}: {detail}')
        self.status = status
        self.detail = detail


class Api:
    def __init__(self, url):
        self.url = url.rstrip('/') + '/api/v1'
        self.access_token = None
        self.refresh_token = None

    def request(self, method, path, payload=None, *, refresh=True):
        headers = {'Content-Type': 'application/json'}
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=10) as response:
                body = response.read()
                return json.loads(body) if body else None
        except HTTPError as error:
            if error.code == HTTPStatus.UNAUTHORIZED and refresh and self.refresh_token:
                tokens = self.request(
                    'POST',
                    '/auth/refresh',
                    {'refresh_token': self.refresh_token},
                    refresh=False,
                )
                self.set_tokens(tokens)
                return self.request(method, path, payload, refresh=False)
            body = error.read().decode()
            try:
                detail = json.loads(body).get('detail', body)
            except ValueError:
                detail = body
            raise ApiError(error.code, detail) from error

    def set_tokens(self, tokens):
        self.access_token = tokens['access_token']
        self.refresh_token = tokens['refresh_token']


def play_turn(api, state, actor, action_code):
    actions = [action_code] if action_code else list(state['available_actions'])
    if action_code and action_code not in state['available_actions']:
        raise RuntimeError(f'Действие {action_code!r} недоступно. Доступны: {state["available_actions"]}')
    random.shuffle(actions)
    enemy = next(participant for participant in state['participants'] if participant['side'] != actor['side'])
    for action in actions:
        # API не возвращает target_policy: при неверной цели попробуем себя.
        for target in (enemy, actor):
            try:
                api.request(
                    'POST',
                    f'/fights/{state["id"]}/actions',
                    {
                        'action_code': action,
                        'target_participant_id': target['id'],
                        'idempotency_key': str(uuid4()),
                        'expected_version': state['version'],
                    },
                )
            except ApiError as error:
                if error.status == HTTPStatus.UNPROCESSABLE_ENTITY and error.detail == 'invalid_fight_action':
                    continue
                if error.status == HTTPStatus.CONFLICT and error.detail in {
                    'stale_fight_version',
                    'not_your_turn',
                    'turn_expired',
                    'fight_finished',
                }:
                    return False
                raise
            print(f'Ход {state["turn_number"]}: {action} → {target["display_name"]}', flush=True)
            return True
    raise RuntimeError('Не удалось выполнить доступные действия. Проверь их эффекты и формулы в админке.')


def rest_character(api, character):
    try:
        api.request('POST', f'/characters/{character["id"]}/rest')
    except ApiError as error:
        if error.status != HTTPStatus.CONFLICT or error.detail != 'character_busy':
            raise
        return False
    print('Здоровье врага восстановлено.', flush=True)
    return True


def run_bot(api, character, delay, actions, rest=True):
    fight_id = None
    action_index = 0
    needs_rest = rest
    while True:
        try:
            state = api.request('GET', '/fights/active')
        except ApiError as error:
            if error.status != HTTPStatus.NOT_FOUND or error.detail != 'fight_not_found':
                raise
            if needs_rest:
                needs_rest = not rest_character(api, character)
            if fight_id:
                print('Бой завершён. Жду следующего.', flush=True)
                fight_id = None
            time.sleep(delay)
            continue

        if state['id'] != fight_id:
            fight_id = state['id']
            action_index = 0
            needs_rest = rest
            print(f'Бой: {state["title"]} ({fight_id})', flush=True)
        if state['status'] in {'started', 'in_progress'}:
            actor = next(
                participant for participant in state['participants'] if participant['source_id'] == character['id']
            )
            if state['active_participant_id'] == actor['id']:
                action_code = actions[action_index % len(actions)] if actions else None
                if play_turn(api, state, actor, action_code):
                    action_index += 1
        time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--login', required=True, help='Логин аккаунта врага')
    parser.add_argument('--url', default='http://127.0.0.1:8000', help='Адрес приложения')
    parser.add_argument('--delay', type=float, default=1, help='Пауза между опросами в секундах (по умолчанию 1)')
    parser.add_argument(
        '--actions',
        '--action',
        nargs='+',
        metavar='CODE',
        help='Повторять действия по порядку: attack heal attack. Без параметра — случайный выбор',
    )
    parser.add_argument(
        '--rest',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Восстанавливать здоровье врага после боя (по умолчанию включено)',
    )
    args = parser.parse_args()
    if not 0 < args.delay < MAX_DELAY:
        parser.error('--delay должен быть больше 0 и меньше 30 секунд')

    try:
        password = os.environ.get('BOT_PASSWORD') or getpass.getpass('Пароль врага: ')
        api = Api(args.url)
        api.set_tokens(api.request('POST', '/auth/login', {'login': args.login, 'password': password}, refresh=False))
        characters = api.request('GET', '/characters')
        if not characters:
            parser.exit(1, 'У аккаунта нет персонажа. Создай его через API или админку.\n')
        character = characters[0]
        api.request('POST', f'/characters/{character["id"]}/select')
        print(f'Враг: {character["nickname"]} ({character["id"]}). Жду боя. Ctrl+C — остановка.', flush=True)
        run_bot(api, character, args.delay, args.actions, args.rest)
    except KeyboardInterrupt:
        print('\nАвтобой остановлен.')
    except (ApiError, URLError, RuntimeError) as error:
        parser.exit(1, f'Ошибка: {error}\n')


if __name__ == '__main__':
    main()
