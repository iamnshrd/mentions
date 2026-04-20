from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

MODEL_NAME = os.getenv('MENTIONS_EMBED_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
DEVICE = os.getenv('MENTIONS_EMBED_DEVICE', 'cuda')

app = FastAPI(title='mentions-gpu-worker')
_model = None


class EmbedRequest(BaseModel):
    texts: List[str]


class Segment(BaseModel):
    id: str | int
    text: str
    meta: Optional[dict] = None


class SemanticSearchRequest(BaseModel):
    family: str
    query: str
    segments: List[Segment]
    top_k: int = 5


class FamilyScoreRequest(BaseModel):
    family: str
    query: str
    event_title: str = ''
    segments: List[Segment]
    top_k: int = 5


class NewsArticle(BaseModel):
    id: str | int
    headline: str
    text: str = ''
    source: str = ''
    meta: Optional[dict] = None


class NewsScoreRequest(BaseModel):
    family: str
    query: str
    event_title: str = ''
    articles: List[NewsArticle]
    top_k: int = 5


@app.on_event('startup')
def _startup() -> None:
    global _model
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer(MODEL_NAME, device=DEVICE)


@app.get('/health')
def health() -> dict:
    return {
        'status': 'ok',
        'model': MODEL_NAME,
        'device': DEVICE,
    }


@app.post('/embed')
def embed(req: EmbedRequest) -> dict:
    vectors = _model.encode(req.texts, normalize_embeddings=True)
    return {
        'status': 'ok',
        'model': MODEL_NAME,
        'count': len(req.texts),
        'vectors': vectors.tolist(),
    }


@app.post('/semantic-search')
def semantic_search(req: SemanticSearchRequest) -> dict:
    texts = [seg.text for seg in req.segments]
    if not texts:
        return {'status': 'ok', 'family': req.family, 'results': []}

    query_vec = _model.encode([req.query], normalize_embeddings=True)[0]
    seg_vecs = _model.encode(texts, normalize_embeddings=True)

    results = []
    for seg, vec in zip(req.segments, seg_vecs):
        score = float((query_vec * vec).sum())
        results.append({
            'id': seg.id,
            'score': score,
            'text': seg.text,
            'meta': seg.meta or {},
        })

    results.sort(key=lambda row: row['score'], reverse=True)
    return {
        'status': 'ok',
        'family': req.family,
        'model': MODEL_NAME,
        'results': results[: max(1, req.top_k)],
    }


@app.post('/family-score')
def family_score(req: FamilyScoreRequest) -> dict:
    texts = [seg.text for seg in req.segments]
    if not texts:
        return {'status': 'ok', 'family': req.family, 'results': []}

    query_text = ' '.join(part for part in [req.family, req.query, req.event_title] if part).strip()
    query_vec = _model.encode([query_text], normalize_embeddings=True)[0]
    seg_vecs = _model.encode(texts, normalize_embeddings=True)

    results = []
    for seg, vec in zip(req.segments, seg_vecs):
        score = float((query_vec * vec).sum())
        text = (seg.text or '').lower()
        evidence_type = 'core'
        trade_legal_terms = [
            'tariff', 'tariffs', 'duty', 'duties', 'import', 'imports', 'imported',
            'court', 'supreme court', 'legal', 'trade authority', 'executive authority',
            'authority to impose', 'impose tariffs', 'tariff authority', 'trade deficits'
        ]
        trade_industry_terms = [
            'factory', 'factories', 'manufacturing', 'manufacturing jobs', 'industrial jobs',
            'plant', 'plants', 'plants opening', 'factory opening', 'factory openings',
            'production return', 'production returning', 'steel mill', 'assembly line'
        ]
        energy_industry_terms = [
            'energy production', 'drilling', 'refinery', 'pipeline', 'natural gas production',
            'power plant', 'electric grid', 'electricity production', 'energy infrastructure',
            'grid buildout', 'power generation'
        ]
        broad_economy_terms = [
            'economy', 'inflation', 'prices', 'affordability', 'cost of living', 'gas prices',
            'grocery prices', 'consumer prices', 'jobs', 'wages', 'interest rates'
        ]
        border_terms = [
            'border', 'illegal aliens', 'immigration', 'migrants', 'deportation', 'deportations',
            'crossing the border', 'border security', 'cartel', 'asylum', 'crossings',
            'remain in mexico', 'wall', 'border patrol', 'illegal immigration', 'migrant crime'
        ]
        healthcare_terms = [
            'drug prices', 'prescription drugs', 'healthcare costs', 'health care costs',
            'most favored nation', 'most-favored-nation', 'rural health', 'medicaid',
            'patient affordability', 'pharmaceutical', 'drug pricing', 'prescription costs',
            'drug companies', 'big pharma', 'patient costs'
        ]
        sports_terms = [
            'college sports', 'nil', 'student athletes', 'university', 'universities',
            'ncaa', 'college football', 'college basketball', 'education system',
            'sports governance'
        ]
        gop_internal_terms = [
            'house gop', 'member retreat', 'republican conference', 'gop', 'coalition',
            'conference meeting', 'republican members', 'house republicans'
        ]
        agriculture_terms = [
            'farmers', 'farmer', 'agriculture', 'crops', 'farm production', 'john deere',
            'rural producers', 'food prices', 'farm country', 'farmers were crushed',
            'farm relief', 'rural america'
        ]
        opponents_terms = [
            'biden', 'kamala', 'obama', 'democrat', 'fake news', 'newscum',
            'political enemies', 'witch hunt', 'radical left', 'crooked', 'enemy of the people'
        ]
        boast_terms = ['right about everything', 'hottest economy', 'everybody knows it', 'they all know it', 'congratulations']
        generic_economy_terms = ['economy', 'invested in our country', 'new plants opening', 'bad economy']

        if req.family == 'broad_economy_prices':
            if any(term in text for term in boast_terms):
                evidence_type = 'generic_regime'
            else:
                evidence_type = 'spillover'
        elif any(term in text for term in boast_terms) or any(term in text for term in generic_economy_terms):
            evidence_type = 'generic_regime'
        elif req.family == 'tariff_policy_legal' and any(term in text for term in ['ship', 'hull', 'stealth', 'gorgeous']):
            evidence_type = 'spillover'
        elif req.family == 'tariff_policy_legal' and not any(term in text for term in trade_legal_terms):
            evidence_type = 'spillover'
        elif req.family == 'trade_industry_manufacturing' and any(term in text for term in [
            'critical minerals', 'minerals reserve', 'stockpile', 'strategic reserve',
            'rare earth', 'critical materials', 'industrial policy'
        ]):
            evidence_type = 'spillover'
        elif req.family == 'trade_industry_manufacturing' and not any(term in text for term in trade_industry_terms):
            evidence_type = 'spillover'
        elif req.family == 'energy_industry_manufacturing' and any(term in text for term in [
            'critical minerals', 'minerals reserve', 'stockpile', 'strategic reserve', 'rare earth',
            'rich because of tariffs', 'tariffs', 'oil prices', 'gas prices'
        ]):
            evidence_type = 'spillover'
        elif req.family == 'energy_industry_manufacturing' and any(term in text for term in boast_terms):
            evidence_type = 'generic_regime'
        elif req.family == 'energy_industry_manufacturing' and any(term in text for term in broad_economy_terms):
            evidence_type = 'spillover'
        elif req.family == 'energy_industry_manufacturing' and not any(term in text for term in energy_industry_terms):
            evidence_type = 'spillover'
        elif req.family == 'border_immigration' and any(term in text for term in boast_terms):
            evidence_type = 'generic_regime'
        elif req.family == 'border_immigration' and any(term in text for term in ['kamala', 'biden', 'obama', 'democrat', 'fake news']):
            evidence_type = 'spillover'
        elif req.family == 'border_immigration' and any(term in text for term in ['law enforcement', 'vital interests', 'strength', 'defend the core', 'keep america safe and free']):
            evidence_type = 'spillover'
        elif req.family == 'border_immigration' and not any(term in text for term in border_terms):
            evidence_type = 'spillover'
        elif req.family == 'healthcare_drug_pricing' and any(term in text for term in boast_terms):
            evidence_type = 'generic_regime'
        elif req.family == 'healthcare_drug_pricing' and any(term in text for term in ['eli lilly', 'merck', 'pfizer', 'drug companies', 'big pharma']):
            if any(term in text for term in ['drug prices', 'prescription drugs', 'drug pricing', 'patient costs', 'prescription costs']):
                evidence_type = 'core'
            else:
                evidence_type = 'spillover'
        elif req.family == 'healthcare_drug_pricing' and any(term in text for term in ['medicaid', 'most favored nation', 'most-favored-nation', 'patient affordability']):
            evidence_type = 'core'
        elif req.family == 'healthcare_drug_pricing' and any(term in text for term in broad_economy_terms):
            evidence_type = 'spillover'
        elif req.family == 'healthcare_drug_pricing' and any(term in text for term in ['congratulations', 'new plants opening', 'record', 'very much']):
            evidence_type = 'generic_regime'
        elif req.family == 'healthcare_drug_pricing' and not any(term in text for term in healthcare_terms):
            evidence_type = 'spillover'
        elif req.family == 'sports_education_institutions' and any(term in text for term in boast_terms):
            evidence_type = 'generic_regime'
        elif req.family == 'sports_education_institutions' and any(term in text for term in ['biden', 'kamala', 'obama', 'democrat', 'fake news']):
            evidence_type = 'spillover'
        elif req.family == 'sports_education_institutions' and not any(term in text for term in sports_terms):
            evidence_type = 'spillover'
        elif req.family == 'gop_coalition_internal' and any(term in text for term in boast_terms):
            evidence_type = 'generic_regime'
        elif req.family == 'gop_coalition_internal' and any(term in text for term in ['kamala', 'biden', 'obama', 'democrat', 'fake news']):
            evidence_type = 'spillover'
        elif req.family == 'gop_coalition_internal' and not any(term in text for term in gop_internal_terms):
            evidence_type = 'spillover'
        elif req.family == 'agriculture_farmers' and any(term in text for term in boast_terms):
            evidence_type = 'generic_regime'
        elif req.family == 'agriculture_farmers' and any(term in text for term in ['tariffs', 'trade deficits', 'economy']):
            evidence_type = 'spillover'
        elif req.family == 'agriculture_farmers' and any(term in text for term in broad_economy_terms):
            evidence_type = 'spillover'
        elif req.family == 'agriculture_farmers' and not any(term in text for term in agriculture_terms):
            evidence_type = 'spillover'
        elif req.family == 'opponents_media_attacks' and any(term in text for term in boast_terms):
            evidence_type = 'generic_regime'
        elif req.family == 'opponents_media_attacks' and any(term in text for term in ['house republican conference', 'member retreat', 'house gop', 'conference']):
            evidence_type = 'spillover'
        elif req.family == 'opponents_media_attacks' and not any(term in text for term in opponents_terms):
            evidence_type = 'spillover'
        elif req.family == 'war_geopolitics' and not any(term in text for term in ['iran', 'war', 'military', 'missile', 'missiles', 'nato', 'ukraine', 'security']):
            evidence_type = 'spillover'
        results.append({
            'id': seg.id,
            'score': score,
            'text': seg.text,
            'meta': seg.meta or {},
            'evidence_type': evidence_type,
        })

    results.sort(key=lambda row: row['score'], reverse=True)
    return {
        'status': 'ok',
        'family': req.family,
        'model': MODEL_NAME,
        'results': results[: max(1, req.top_k)],
    }


@app.post('/news-score')
def news_score(req: NewsScoreRequest) -> dict:
    texts = [f"{article.headline} {article.text}".strip() for article in req.articles]
    if not texts:
        return {'status': 'ok', 'family': req.family, 'results': []}

    query_text = ' '.join(part for part in [req.family, req.query, req.event_title] if part).strip()
    query_vec = _model.encode([query_text], normalize_embeddings=True)[0]
    article_vecs = _model.encode(texts, normalize_embeddings=True)

    event_terms = ['roundtable', 'event', 'speech', 'remarks', 'attend', 'venue', 'las vegas', 'no-show', 'appearance']
    economy_terms = ['tariffs', 'inflation', 'prices', 'economy', 'jobs', 'wages', 'gas prices']
    opposition_terms = ['critics', 'campaign-style stunt', 'opponents', 'media reaction', 'democrats', 'criticism']
    geopolitics_terms = ['iran', 'war', 'missiles', 'ukraine', 'china', 'israel']
    logistics_terms = ['no-show', 'venue', 'attendance', 'scheduled', 'local officials', 'las vegas']

    results = []
    for article, vec, text in zip(req.articles, article_vecs, texts):
        score = float((query_vec * vec).sum())
        blob = text.lower()
        evidence_type = 'topic_expansion'
        if req.family == 'direct_event_coverage':
            if any(term in blob for term in ['roundtable', 'venue', 'attendance', 'no-show', 'las vegas', 'scheduled', 'appearance']):
                evidence_type = 'event_core'
            elif any(term in blob for term in opposition_terms + economy_terms + geopolitics_terms):
                evidence_type = 'topic_expansion'
            else:
                evidence_type = 'topic_expansion'
        elif req.family == 'policy_rollout':
            if any(term in blob for term in ['policy', 'announcement', 'plan', 'proposal', 'no tax on tips']):
                evidence_type = 'event_core'
            else:
                evidence_type = 'topic_expansion'
        elif req.family == 'local_event_logistics':
            if any(term in blob for term in logistics_terms):
                evidence_type = 'event_core'
            else:
                evidence_type = 'topic_expansion'
        elif req.family == 'broader_economy_regime':
            evidence_type = 'ambient_regime' if any(term in blob for term in economy_terms) else 'topic_expansion'
        elif req.family == 'geopolitics_ambient':
            evidence_type = 'ambient_regime' if any(term in blob for term in geopolitics_terms) else 'topic_expansion'
        elif req.family == 'opposition_media_reaction':
            evidence_type = 'topic_expansion' if any(term in blob for term in opposition_terms) else 'topic_expansion' if 'critics say' in blob or 'campaign-style stunt' in blob else 'ambient_regime'
        results.append({
            'id': article.id,
            'score': score,
            'headline': article.headline,
            'text': article.text,
            'source': article.source,
            'meta': article.meta or {},
            'family': req.family,
            'evidence_type': evidence_type,
        })

    results.sort(key=lambda row: row['score'], reverse=True)
    return {
        'status': 'ok',
        'family': req.family,
        'model': MODEL_NAME,
        'results': results[: max(1, req.top_k)],
    }


if __name__ == '__main__':
    import uvicorn
    host = os.getenv('MENTIONS_WORKER_HOST', '0.0.0.0')
    port = int(os.getenv('MENTIONS_WORKER_PORT', '8765'))
    uvicorn.run(app, host=host, port=port)
