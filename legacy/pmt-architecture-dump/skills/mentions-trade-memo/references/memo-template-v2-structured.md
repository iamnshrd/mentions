# Structured Market Memo Template v2

Use this for investor-style market writeups and Telegram-ready market reports.

## Output shape

### 1) Event header
- **Название события:** human-readable event title, not raw event shorthand
- **Тема / место / формат / предполагаемая длительность:** one compact line
- **Гости / Q&A:**
  - Будут ли говорить гости
  - Будет ли сессия Q&A
- **Уровень рынка:** легкий / средний / тяжелый
- **Market regime:** Y fest / N fest / mixed

### 2) Core read
One short paragraph:
- what the format really is
- what the market is most likely getting right
- what the market is most likely getting wrong

### 3) Basket breakdown
For each basket, use this structure:

#### [Basket name]
- **Тезис:** what this basket is expressing
- **Почему:** 2-4 bullets on structure / format / topic-tree logic
- **Win condition:** what has to happen for the basket to work
- **Invalidation:** what breaks the basket thesis

Then list strikes under the basket in bullets:
- `` `Strike label` `` — current price X / FV Y — short reasoning

Basket labels should normally be one of:
- **Основная YES корзина**
- **Поздние темы / Q&A корзина**
- **Средняя / Избирательно**
- **Пассивные NO**
- **No-touch**

### 4) Final execution view
- **Лучшая корзина:** one line
- **Main pricing signal:** one line
- **Main crowd mistake:** one line
- **Relevant phase logic:** one line
- **Closest case:** one line if helpful
- **Execution:** limit / wait / passive NO / selective YES / avoid
- **Sizing:** small / normal / press / avoid sizing up

## Rules
- Before writing prose, consult `/root/.openclaw/workspace/wording/markets_wording_db.json` and follow it as the wording source of truth.
- Use the exact user-approved replacements from the wording DB; do not improvise around them when a stored phrase already exists.
- Use human-readable strike labels only, in monospace
- Include both current price and rough FV for every strike mentioned
- Include invalidation at basket level always
- Include strike-level invalidation only when needed
- Include win condition at basket level always
- Include strike-level win condition only when needed
- Prefer compact readable prose over exhaustive dumps
- If the event context is uncertain or stale, say that explicitly
