from __future__ import annotations

"""Transcript family taxonomy v0.

Hybrid design:
- some families emerge well from unsupervised clustering
- some remain prompt-guided / semi-supervised because they are sparse or too event-specific
"""

TRANSCRIPT_FAMILY_TAXONOMY_V0 = {
    'tariff_policy_legal': {
        'description': 'Tariffs, trade authority, court fights over tariff powers, import duties, and legal or executive authority framing.',
        'mode': 'semantic_hybrid',
        'expression': 'regime_embedded',
        'cluster_hints': [2],
        'prompts': [
            'discussion of tariffs, trade authority, court rulings on tariffs, import duties, executive authority to impose tariffs, supreme court or legal fights around tariffs',
            'discussion of tariff policy, trade deficits, tariff legality, tariff authority, import duties and legal power',
        ],
        'spillovers': ['broad_economy_prices', 'agriculture_farmers'],
    },
    'trade_industry_manufacturing': {
        'description': 'Factories, manufacturing return, steel, industrial revival, production buildout, and trade-linked industry rhetoric.',
        'mode': 'semantic_hybrid',
        'expression': 'regime_embedded',
        'cluster_hints': [4],
        'prompts': [
            'discussion of factories returning, steel, manufacturing revival, industrial production, plants, production buildout because of trade policy',
            'discussion of car industry, manufacturing jobs, industrial buildout, factories, steel and domestic production',
        ],
        'spillovers': ['energy_industry_manufacturing', 'broad_economy_prices'],
    },
    'election_mandate': {
        'description': 'Victory rhetoric, landslide claims, swing states, mandate language, political boasting.',
        'cluster_hints': [1, 3],
        'prompts': [
            'discussion of election victory, landslide, swing states, mandate, political win, too big to rig',
        ],
        'spillovers': ['gop_coalition_internal', 'opponents_media_attacks'],
    },
    'war_geopolitics': {
        'description': 'Iran, war, missiles, terror, national security, military operations, hard-power rhetoric.',
        'mode': 'semantic_native',
        'expression': 'direct_core',
        'cluster_hints': [6, 9],
        'prompts': [
            'discussion of iran, war, missiles, military operations, terror, national security, china, israel, hard power',
            'discussion of military strikes, war front, national security threats, terror proxies, missiles, navy, iran regime',
        ],
        'spillovers': ['energy_industry_manufacturing', 'opponents_media_attacks'],
    },
    'healthcare_drug_pricing': {
        'description': 'Drug prices, healthcare costs, most-favored-nation pricing, rural health, patient cost relief.',
        'mode': 'semantic_native',
        'expression': 'direct_core',
        'cluster_hints': [7],
        'prompts': [
            'discussion of healthcare costs, drug pricing, most favored nation pricing, rural health, medicaid waste, patient affordability',
        ],
        'spillovers': ['broad_economy_prices'],
    },
    'border_immigration': {
        'description': 'Border security, illegal immigration, enforcement, crime-adjacent security rhetoric.',
        'mode': 'semantic_hybrid',
        'expression': 'direct_core',
        'cluster_hints': [5],
        'prompts': [
            'discussion of border security, illegal aliens, immigration enforcement, criminals crossing the border',
        ],
        'spillovers': ['war_geopolitics', 'opponents_media_attacks'],
    },
    'energy_industry_manufacturing': {
        'description': 'Energy production, steel, plants, manufacturing, infrastructure, industrial buildout.',
        'mode': 'semantic_hybrid',
        'expression': 'regime_embedded',
        'cluster_hints': [4, 8],
        'prompts': [
            'discussion of energy, manufacturing, steel, industrial plants, infrastructure, production, factories',
        ],
        'spillovers': ['trade_tariffs', 'broad_economy_prices'],
    },
    'sports_education_institutions': {
        'description': 'College sports, NIL, institutional survival, education-system governance via sports.',
        'mode': 'semantic_native',
        'expression': 'direct_core',
        'cluster_hints': [0],
        'prompts': [
            'discussion of college sports, NIL, universities, education system, institutional survival through sports governance',
        ],
        'spillovers': ['opponents_media_attacks'],
    },
    'gop_coalition_internal': {
        'description': 'House GOP, member retreats, coalition management, party persuasion, internal Republican room rhetoric.',
        'mode': 'semantic_hybrid',
        'expression': 'regime_embedded',
        'cluster_hints': [3, 5],
        'prompts': [
            'discussion of house republicans, member retreat, republican conference, coalition management, internal party persuasion',
        ],
        'spillovers': ['election_mandate', 'opponents_media_attacks'],
    },
    'broad_economy_prices': {
        'description': 'Inflation, prices, affordability, consumer cost rhetoric, broad economic performance framing.',
        'mode': 'semantic_hybrid',
        'expression': 'regime_embedded',
        'cluster_hints': [2, 4, 8],
        'prompts': [
            'discussion of inflation, prices, affordability, consumers, economy, cost of living, grocery prices',
        ],
        'spillovers': ['trade_tariffs', 'energy_industry_manufacturing', 'healthcare_drug_pricing'],
    },
    'labor_service_workers': {
        'description': 'Service workers, tipped workers, delivery workers, restaurant/hospitality labor, wages, working families.',
        'mode': 'prompt_guided',
        'expression': 'regime_embedded',
        'cluster_hints': [],
        'prompts': [
            'discussion of tipped workers, service workers, restaurant workers, delivery drivers, hospitality labor, wages, workers keeping more of their tips',
            'discussion of no tax on tips, tipped income, restaurant workers, delivery drivers, waiters, waitresses, hospitality workers',
        ],
        'spillovers': ['broad_economy_prices', 'trade_tariffs'],
        'exclude_terms': ['iran', 'war', 'missiles', 'military', 'border', 'illegal aliens', 'sports', 'basketball'],
        'note': 'This family does not yet emerge strongly from unsupervised clustering and should remain prompt-guided / semi-supervised for now.',
    },
    'agriculture_farmers': {
        'description': 'Farmers, crops, farm production, agricultural relief, John Deere, food prices, rural production.',
        'mode': 'semantic_hybrid',
        'expression': 'regime_embedded',
        'cluster_hints': [8],
        'prompts': [
            'discussion of farmers, agriculture, crops, farm production, john deere, rural producers, food prices',
        ],
        'spillovers': ['trade_tariffs', 'broad_economy_prices', 'energy_industry_manufacturing'],
    },
    'opponents_media_attacks': {
        'description': 'Attacks on democrats, media, fake news, political enemies, grievance rhetoric.',
        'mode': 'semantic_hybrid',
        'expression': 'regime_embedded',
        'cluster_hints': [1],
        'prompts': [
            'discussion attacking democrats, biden, obama, media, fake news, political enemies, grievance rhetoric',
        ],
        'spillovers': ['election_mandate', 'gop_coalition_internal', 'border_immigration'],
    },
}
