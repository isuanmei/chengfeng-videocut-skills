---
name: talking-head-rough-cut
description: Build a conservative first-pass rough cut for talking-head course or tutorial videos. Use when the user asks to rough cut a lecture, course recording, screen-recorded narration, or talking-head video by removing long silences, obvious failed starts, repeated sentences, abandoned fragments, and severe stutters while keeping a reviewable deletion report and optional rendered MP4.
---

# Talking Head Rough Cut

## Workflow

Use this skill for the first editing pass. The goal is a reviewable rough cut, not a tight final edit.

1. Locate the source video and avoid overwriting it.
2. Get word-level transcript timestamps. Prefer an existing Whisper JSON or `subtitles_words.json`; otherwise transcribe first with the local project workflow.
3. Run `scripts/build_rough_cut.py` to generate:
   - `rough_delete_segments.json`
   - `rough_cut_report.md`
   - optional rendered `*_rough_cut.mp4`
4. Inspect the report before rendering when the source is a course/tutorial.
5. Keep the rough cut conservative: preserve teaching rhythm, intentional thinking pauses, examples, and transitions.

## Command

```bash
python3 /path/to/talking-head-rough-cut/scripts/build_rough_cut.py \
  --input "/path/to/source.mp4" \
  --transcript "/path/to/whisper.json" \
  --output-dir "/path/to/output" \
  --render
```

Use `--plan-only` when only a deletion plan is needed. Use `--encoder x264` if VideoToolbox fails.

## Cut Rules

Prefer deleting:

- silence longer than about `0.85s`, while leaving short breathing room on both sides;
- repeated sentence starts where a later take is cleaner;
- short abandoned fragments before a corrected sentence;
- obvious stutters like `就是就是` or `那个那个`;
- isolated filler syllables only when they stand alone, such as a lone `嗯` between pauses.

Avoid deleting:

- short pauses that help comprehension;
- transition words that carry structure;
- examples or demonstrations that look visually slow but are pedagogically useful;
- any range where transcript and audio timing disagree.

## Handoff To Fine Cut

Pass `rough_delete_segments.json` to `$talking-head-fine-cut` as `--base-delete`. The fine cut should be more aggressive about filler words and pacing.
