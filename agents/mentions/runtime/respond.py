"""Response rendering entrypoint."""
from __future__ import annotations

import logging

from agents.mentions.config import get_default_store
from agents.mentions.presentation.response_renderer import render_user_response
from agents.mentions.runtime.frame import select_frame
from agents.mentions.runtime.retrieve import retrieve_bundle_for_frame
from agents.mentions.runtime.synthesize import synthesize as do_synthesize
from agents.mentions.utils import timed

log = logging.getLogger('mentions')


@timed('respond')
def respond(query: str, mode: str = 'deep', output_format: str = 'text',
            frame: dict | None = None, synthesis: dict | None = None,
            user_id: str = 'default', store=None) -> str:
    store = store or get_default_store()

    if frame is None:
        frame = select_frame(query, user_id=user_id, store=store)
    if synthesis is None:
        bundle = retrieve_bundle_for_frame(query, frame)
        synthesis = do_synthesize(query, frame, bundle)

    rendered = render_user_response(
        query=query,
        frame=frame,
        synthesis=synthesis,
        mode=mode,
        output_format=output_format,
    )

    try:
        from agents.mentions.storage.runtime_db import insert_analysis_report
        evidence_bundle = {
            'frame': frame,
            'query': query,
        }
        insert_analysis_report(
            query=query,
            ticker=(synthesis.get('resolved_market', {}) or {}).get('ticker', ''),
            workflow_policy=synthesis.get('policy_context', {}) or {},
            evidence=evidence_bundle,
            analysis=synthesis,
            rendered_text=rendered,
            metadata={'runtime_phase': 'respond'},
        )
    except Exception as exc:
        log.debug('insert_analysis_report failed during respond: %s', exc)

    return rendered
