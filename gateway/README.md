# OpenClaw Gateway

Эта папка хранит локальные шаблоны для официального OpenClaw Gateway.

Идея такая:

- upstream `openclaw` отвечает за transport, pairing, dashboard и маршрутизацию каналов
- OpenClaw-facing workspace лежит в `openclaw-workspace/`
- локальный runtime `mentions_core` используется как tool/runtime слой внутри workspace
- в локальном gateway-конфиге модель закреплена как `openai-codex/gpt-5.4`, чтобы использовать OAuth-профиль OpenClaw и не требовать `OPENAI_API_KEY`
- агент `mentions` запускается как ACP agent через `acpx` backend с harness `codex`

Этот паттерн ближе к `jordan`: OpenClaw снаружи, а доменная логика живёт в локальном CLI/runtime.

## Быстрый старт

1. Установить официальный OpenClaw CLI:

```bash
npm install -g openclaw@latest
```

2. Скопировать шаблон конфига:

```bash
cp gateway/openclaw.local.example.json5 gateway/openclaw.local.json5
```

3. При необходимости поправить путь `workspace` в конфиге.
По умолчанию он указывает на `openclaw-workspace/`, а не на корень репозитория.

4. Запустить Gateway с локальным конфигом:

```bash
OPENCLAW_CONFIG_PATH="$PWD/gateway/openclaw.local.json5" openclaw gateway
```

Или короче через helper-скрипт из репо:

```bash
./gateway/run-local-gateway.sh
```

5. Одобрить pairing для Telegram:

```bash
OPENCLAW_CONFIG_PATH="$PWD/gateway/openclaw.local.json5" openclaw pairing list telegram
OPENCLAW_CONFIG_PATH="$PWD/gateway/openclaw.local.json5" openclaw pairing approve telegram <CODE>
```

6. Для Telegram DM не используй static `bindings[].type="acp"` в конфиге.

По актуальной документации OpenClaw top-level ACP bindings для Telegram предназначены для persistent bindings на topics. Для обычной лички правильный путь — slash-команда прямо в чате с ботом:

```text
/acp spawn codex --bind here --cwd /tmp/mentions-openclaw-workspace
```

Это создаст current-conversation ACP binding в текущем DM.

7. После этого отправь обычное сообщение в тот же чат и проверь ответ.

`openclaw agent --local` и обычный embedded turn проверяют другой execution path и не подтверждают, что Telegram conversation действительно привязана к ACP session.

## Workspace model

OpenClaw должен читать bootstrap-файлы из `openclaw-workspace/`.
Сам код агента при этом остаётся в родительском репозитории и вызывается через:

```bash
mentionsctl answer mentions "<query>"
mentionsctl run mentions "<query>"
mentionsctl prompt mentions "<query>" --system-only
```

Для Telegram slash-команд удобнее использовать короткий symlink без пробелов:

```bash
/tmp/mentions-openclaw-workspace
```

## Telegram

Шаблон конфига рассчитывает на `TELEGRAM_BOT_TOKEN` из локального `.env`.
Согласно официальной документации OpenClaw, env fallback поддерживается для default account Telegram.
