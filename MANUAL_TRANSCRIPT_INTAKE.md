# Manual Transcript Intake

## Goal

Provide a user-first manual transcript intake path for V1.

The user supplies the transcript and any metadata they already know.
The system stores that metadata as primary truth.
The system may then propose missing tags or normalization hints, but must not overwrite user-provided values.

## Policy

Precedence order:
1. user-provided metadata
2. user-provided tags
3. system-suggested tags
4. system-inferred fallbacks

## Required user fields
- transcript file or text
- speaker
- event

## Optional user fields
- event_date
- format tags
- topic tags
- event tags
- mention tags
- quality tags
- notes

## System behavior after intake
- register transcript
- persist transcript and segments
- keep user-provided metadata unchanged
- generate suggested tags only as a secondary layer
- store both user tags and suggested tags
- expose merged effective tags for retrieval

## V1 storage model
For V1, transcript tag storage keeps both:
- user-provided tags
- suggested tags

and also stores merged effective tags for retrieval.

This gives a practical compromise:
- user truth is preserved
- retrieval remains simple
- suggestions can still help fill gaps

## First implementation goal
The first implementation does not need a full UI.
It only needs a clean contract so a manual transcript can be ingested with:
- user-first metadata
- suggested-tag persistence
- retrieval-usable merged tags
