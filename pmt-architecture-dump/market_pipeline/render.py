#!/usr/bin/env python3
import json, sys

# Assumes wording-db checks have already happened upstream.

def render_report(data):
    def line(label, value):
        if value is None or value == '':
            value = '—'
        return f"- **{label}:** {value}"

    def render_basket(b):
        out=[]
        out.append(f"## {b.get('name','Basket')}")
        out.append(f"- **Тезис:** {b.get('thesis','—')}")
        out.append(f"- **Win condition:** {b.get('win_condition','—')}")
        out.append(f"- **Invalidation:** {b.get('invalidation','—')}")
        for s in b.get('strikes',[]) or []:
            note = s.get('note','—').replace('buy / core yes', 'YES').replace('selective buy', 'избирательная покупка').replace('passive no', 'пассивный NO')
            out.append(f"- `{s.get('label','—')}` — current **{s.get('current_price','—')}** / FV **{s.get('fv_price','—')}** — {note}")
        return '\n'.join(out)

    best_yes = data.get('best_yes') or '—'
    best_no = data.get('best_no') or '—'
    no_touch = data.get('no_touch') or '—'

    out=[]
    out.append('# Паспорт события')
    out.append(line('Название события', data.get('title','Event')))
    out.append(line('Тема / место / формат / предполагаемая длительность', data.get('topic_line')))
    out.append(line('Будут ли говорить гости / будет ли сессия Q&A', data.get('guests_qa')))
    out.append(line('Уровень рынка', data.get('difficulty')))
    out.append(line('Market regime', data.get('regime')))
    out.append('')
    out.append('# Короткий структурный тезис')
    out.append(data.get('core_read') or '—')
    out.append('')
    out.append('# Лучшая идея')
    out.append(line('Лучшая корзина', data.get('best_basket','—')))
    out.append(line('Лучший YES', best_yes))
    out.append(line('Лучший NO', best_no))
    out.append(line('No-touch', no_touch))
    out.append('')
    for basket in data.get('baskets',[]):
        out.append(render_basket(basket))
        out.append('')
    out.append('# Торговый вывод')
    out.append(line('Main pricing signal', data.get('main_pricing_signal','—')))
    out.append(line('Main crowd mistake', data.get('main_crowd_mistake','—')))
    out.append(line('Relevant phase logic', data.get('relevant_phase_logic','—')))
    out.append(line('Closest case', data.get('closest_case','—')))
    out.append(line('Покупать / шортить', data.get('execution','—')))
    out.append(line('Sizing', data.get('sizing','—')))
    return '\n'.join(out).strip()

def main():
    print(render_report(json.load(sys.stdin)))

if __name__ == '__main__':
    main()
