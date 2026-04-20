from agents.mentions.services.transcripts.knowledge_extraction import extract_transcript_knowledge_bundle


def test_transcript_knowledge_extraction_selects_structured_candidates():
    bundle = extract_transcript_knowledge_bundle(
        'Will Trump mention Iran?',
        {
            'chunks': [
                {
                    'speaker': 'Donald Trump',
                    'event': 'Interview',
                    'text': 'The market was clearly overpriced and fair value was lower. Everyone was chasing the move instead of thinking about edge and odds.',
                },
                {
                    'speaker': 'Donald Trump',
                    'event': 'Interview',
                    'text': 'Limit orders matter because fills and spread control are the whole game in thin books, and execution improves when maker discipline keeps entries patient instead of forcing taker fills into a bad orderbook.',
                },
                {
                    'speaker': 'Donald Trump',
                    'event': 'Interview',
                    'text': 'Historically he often says these things late in Q&A, not in prepared remarks, and he usually tends to circle back to the topic only after the first wave of questions has already set the frame.',
                },
            ]
        },
    )
    assert bundle['status'] == 'ok'
    assert bundle['selected']['main_pricing_signal'] is not None
    assert bundle['selected']['main_execution_pattern'] is not None
    assert bundle['selected']['speaker_tendency'] is not None
