# Documentation

Project documentation that used to live in the repository root has been grouped here to keep the top level focused on runtime entrypoints and config.

## Layout

- `specs/` - architecture, pipeline, and implementation specs
- `notes/` - short retrospective notes that are useful to keep but not worth keeping in the root
- `ui/` - static GitHub Pages workspace frontend and runtime-exported payloads

## Updating the Pages UI with real runtime data

Export a fresh payload into the static UI:

```bash
python -m mentions_core workspace "<query>" --output docs/ui/workspace-data.json
```

The frontend at [`/Users/nshrd/Documents/Mentions/mentions/docs/index.html`](/Users/nshrd/Documents/Mentions/mentions/docs/index.html:1)
will automatically load `docs/ui/workspace-data.json` when it exists, and fall
back to demo data otherwise.
