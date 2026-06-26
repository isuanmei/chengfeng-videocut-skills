---
name: talking-head-fine-cut
description: Build a tighter second-pass fine cut for talking-head course or tutorial videos after a rough cut. Use when the user asks to refine a rough-cut lecture, remove remaining filler words such as 嗯, 啊, 呃, 那个, 这个, 就是, 然后, tighten short pauses, clean repeated starts, or produce a cleaner final MP4 and deletion report from transcript timestamps plus an optional base cut list.
---

# Talking Head Fine Cut

## Workflow

Use this skill after a rough cut or when the user explicitly asks for a tighter final edit.

1. Start from the source video and word-level transcript.
2. Include the rough cut list with `--base-delete` when available.
3. Run `scripts/build_fine_cut.py` to generate:
   - `fine_delete_segments.json`
   - `fine_cut_report.md`
   - optional rendered `*_fine_cut.mp4`
4. Review the added fine-cut ranges, especially ambiguous `那个/这个` removals.
5. Render only after checking that timing and meaning are acceptable.

## Command

```bash
python3 /path/to/talking-head-fine-cut/scripts/build_fine_cut.py \
  --input "/path/to/source.mp4" \
  --transcript "/path/to/whisper.json" \
  --base-delete "/path/to/rough_delete_segments.json" \
  --output-dir "/path/to/output" \
  --style tight \
  --render
```

Use `--style normal` for safer edits. Use `--style tight` when the user complains that too many fillers remain.

## Strong Filler Policy

Default to stronger cleanup than the rough cut:

- Delete standalone filler syllables: `嗯`, `啊`, `呃`, `额`, `欸`, `诶`, `哎`.
- Delete sentence-leading filler words when the sentence still reads naturally: `那个`, `这个`, `就是`, `然后`, `那么`, `其实`, `所以`, `好`, `对吧`.
- Delete repeated filler clusters: `那个那个`, `嗯嗯`, `啊啊`, `就是就是`, `然后然后`.
- Delete short filler-only units even when they are followed by a visual pause.
- Shorten silences more aggressively than rough cut, but do not remove all breathing room.

Keep or mark for review when:

- `那个/这个` appears to point to a visible object, UI element, or previous example;
- removing a transition word breaks the step-by-step teaching flow;
- the edit would cut into a syllable or make the screen action confusing.

## Quality Bar

A fine cut should sound intentionally edited. It should remove leftover filler words that distract from pacing, while preserving course clarity. If in doubt, produce the cut list and report first, then render after review.
