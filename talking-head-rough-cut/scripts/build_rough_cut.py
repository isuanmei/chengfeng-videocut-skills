#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PUNCT_RE = re.compile(r"[\s，。！？、,.!?；;：:“”\"'（）()\[\]{}《》<>~·…—\-_]+")


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Unit:
    text: str
    norm: str
    start: float
    end: float


def run(cmd: list[str | Path], capture: bool = False, log_path: Path | None = None) -> str:
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as fh:
            proc = subprocess.run([str(x) for x in cmd], stdout=fh, stderr=subprocess.STDOUT, text=True)
        if proc.returncode:
            raise SystemExit(f"command failed; see {log_path}")
        return ""
    proc = subprocess.run(
        [str(x) for x in cmd],
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
    )
    if proc.returncode:
        if capture:
            print(proc.stdout or "")
            print(proc.stderr or "", file=sys.stderr)
        raise SystemExit("command failed: " + " ".join(str(x) for x in cmd))
    return (proc.stdout or "") + (proc.stderr or "") if capture else ""


def norm(text: str) -> str:
    return PUNCT_RE.sub("", text).lower()


def duration(path: Path) -> float:
    text = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture=True,
    ).strip()
    return float(text)


def load_words(path: Path) -> list[Word]:
    data = json.loads(path.read_text(encoding="utf-8"))
    words: list[Word] = []
    if isinstance(data, list):
        for item in data:
            if item.get("isGap"):
                continue
            text = re.sub(r"\s+", "", str(item.get("text", "")))
            if text and norm(text):
                words.append(Word(text, float(item["start"]), float(item["end"])))
        return sorted(words, key=lambda w: (w.start, w.end))

    for segment in data.get("segments", []):
        for item in segment.get("words") or []:
            text = re.sub(r"\s+", "", str(item.get("word", "")))
            if text and norm(text):
                words.append(Word(text, float(item.get("start", segment["start"])), float(item.get("end", segment["end"]))))
    return sorted(words, key=lambda w: (w.start, w.end))


def split_units(words: list[Word], gap: float = 0.55, max_chars: int = 42) -> list[Unit]:
    if not words:
        return []
    units: list[Unit] = []
    start = 0
    for idx in range(len(words) - 1):
        text_len = sum(len(w.text) for w in words[start : idx + 1])
        if words[idx + 1].start - words[idx].end >= gap or text_len >= max_chars:
            text = "".join(w.text for w in words[start : idx + 1])
            normalized = norm(text)
            if normalized:
                units.append(Unit(text, normalized, words[start].start, words[idx].end))
            start = idx + 1
    text = "".join(w.text for w in words[start:])
    normalized = norm(text)
    if normalized:
        units.append(Unit(text, normalized, words[start].start, words[-1].end))
    return units


def parse_silences(text: str) -> list[dict]:
    starts: list[float] = []
    silences: list[dict] = []
    for line in text.splitlines():
        start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start:
            starts.append(float(start.group(1)))
            continue
        end = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
        if end and starts:
            s = starts.pop(0)
            e = float(end.group(1))
            silences.append({"start": s, "end": e, "duration": e - s})
    return silences


def detect_silences(video: Path, output_dir: Path, db: str, min_dur: float) -> list[dict]:
    log_path = output_dir / "silencedetect.log"
    text = run(["ffmpeg", "-hide_banner", "-i", video, "-af", f"silencedetect=n={db}:d={min_dur}", "-f", "null", "-"], capture=True)
    log_path.write_text(text, encoding="utf-8")
    silences = parse_silences(text)
    (output_dir / "silences.json").write_text(json.dumps(silences, ensure_ascii=False, indent=2), encoding="utf-8")
    return silences


def add(segments: list[dict], start: float, end: float, reason: str, text: str = "") -> None:
    if end - start >= 0.08:
        segments.append({"start": max(0.0, start), "end": max(0.0, end), "reason": reason, "text": text})


def lcp(a: str, b: str) -> int:
    count = 0
    for left, right in zip(a, b):
        if left != right:
            break
        count += 1
    return count


def rough_segments(words: list[Word], units: list[Unit], silences: list[dict], total: float) -> list[dict]:
    segments: list[dict] = []
    for silence in silences:
        start, end = float(silence["start"]), float(silence["end"])
        dur = end - start
        if start <= 0.2:
            add(segments, 0.0, max(0.0, end - 0.18), "rough: trim leading silence")
        elif total - end <= 0.25:
            add(segments, min(total, start + 0.18), total, "rough: trim trailing silence")
        elif dur >= 0.85:
            pad = 0.46 if dur >= 2.0 else 0.34
            add(segments, start + pad, end - pad, f"rough: shorten silence {dur:.2f}s")

    for idx in range(len(units) - 1):
        curr, nxt = units[idx], units[idx + 1]
        common = lcp(curr.norm, nxt.norm)
        if common >= 5:
            victim = curr if len(curr.norm) <= len(nxt.norm) + 4 else nxt
            add(segments, victim.start, victim.end, "rough: repeated sentence start", victim.text)
        if len(curr.norm) <= 8 and common >= max(3, len(curr.norm) - 1):
            add(segments, curr.start, curr.end, "rough: abandoned fragment before retake", curr.text)

    full_text = "".join(w.text for w in words)
    for phrase in ["那个", "就是", "然后", "这个", "所以", "那么"]:
        for match in re.finditer(re.escape(phrase + phrase), full_text):
            chars_seen = 0
            start_word = end_word = None
            for w in words:
                next_seen = chars_seen + len(w.text)
                if start_word is None and chars_seen <= match.start() < next_seen:
                    start_word = w
                if chars_seen < match.start() + len(phrase) <= next_seen:
                    end_word = w
                    break
                chars_seen = next_seen
            if start_word and end_word:
                add(segments, start_word.start, end_word.end, "rough: repeated filler word", phrase)

    for unit in units:
        if unit.norm in {"嗯", "啊", "呃", "额", "欸", "诶", "哎"} and unit.end - unit.start <= 1.2:
            add(segments, unit.start, unit.end, "rough: isolated filler", unit.text)
    return merge(segments, total)


def merge(segments: list[dict], total: float) -> list[dict]:
    cleaned = []
    for seg in segments:
        start = max(0.0, min(total, float(seg["start"])))
        end = max(0.0, min(total, float(seg["end"])))
        if end - start >= 0.08:
            cleaned.append({**seg, "start": start, "end": end})
    cleaned.sort(key=lambda x: (x["start"], x["end"]))
    merged: list[dict] = []
    for seg in cleaned:
        if not merged or seg["start"] > merged[-1]["end"] + 0.08:
            merged.append(seg.copy())
            continue
        merged[-1]["end"] = max(merged[-1]["end"], seg["end"])
        if seg["reason"] not in merged[-1]["reason"]:
            merged[-1]["reason"] += " + " + seg["reason"]
        if seg.get("text"):
            merged[-1]["text"] = (merged[-1].get("text", "") + " / " + seg["text"]).strip(" /")
    return merged


def keep_intervals(deletes: list[dict], total: float) -> list[dict]:
    keep = []
    cursor = 0.0
    for seg in deletes:
        if seg["start"] > cursor:
            keep.append({"start": cursor, "end": seg["start"]})
        cursor = max(cursor, seg["end"])
    if cursor < total:
        keep.append({"start": cursor, "end": total})
    return [k for k in keep if k["end"] - k["start"] >= 0.08]


def write_report(output_dir: Path, video: Path, out_video: Path, deletes: list[dict], total: float) -> None:
    keep = keep_intervals(deletes, total)
    payload = {"source": str(video), "output": str(out_video), "source_duration": total, "delete_count": len(deletes), "delete_duration": sum(d["end"] - d["start"] for d in deletes), "deletes": deletes, "keep": keep}
    (output_dir / "rough_delete_segments.json").write_text(json.dumps(deletes, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "rough_cut_plan.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Rough Cut Report", "", f"- Source: `{video}`", f"- Output: `{out_video}`", f"- Source duration: {total:.2f}s", f"- Delete count: {len(deletes)}", f"- Delete duration: {payload['delete_duration']:.2f}s", f"- Estimated output: {total - payload['delete_duration']:.2f}s", "", "| start | end | duration | reason | text |", "|---:|---:|---:|---|---|"]
    for seg in deletes:
        lines.append(f"| {seg['start']:.2f} | {seg['end']:.2f} | {seg['end'] - seg['start']:.2f} | {seg['reason']} | {str(seg.get('text', '')).replace('|', '/')[:80]} |")
    (output_dir / "rough_cut_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def render(video: Path, out_video: Path, keep: list[dict], encoder: str, output_dir: Path) -> None:
    expr = "+".join(f"between(t,{k['start']:.3f},{k['end']:.3f})" for k in keep)
    common = ["ffmpeg", "-y", "-hide_banner", "-i", video, "-map", "0:v:0", "-map", "0:a:0", "-vf", f"select='{expr}',setpts=N/25/TB,fps=25,format=yuv420p", "-af", f"aselect='{expr}',asetpts=N/SR/TB,loudnorm=I=-16:TP=-1.5:LRA=11"]
    encoders = [["-c:v", "h264_videotoolbox", "-b:v", "16000k"], ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]] if encoder == "auto" else ([["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]] if encoder == "x264" else [["-c:v", "h264_videotoolbox", "-b:v", "16000k"]])
    last_error = None
    for idx, enc in enumerate(encoders):
        try:
            run(common + enc + ["-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-movflags", "+faststart", out_video], log_path=output_dir / f"render_{idx + 1}.log")
            return
        except SystemExit as exc:
            last_error = exc
    raise SystemExit(last_error)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--transcript", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--encoder", choices=["auto", "x264", "videotoolbox"], default="auto")
    parser.add_argument("--silence-db", default="-35dB")
    parser.add_argument("--silence-min", type=float, default=0.5)
    args = parser.parse_args()

    output_dir = args.output_dir or args.input.with_suffix("").with_name(args.input.stem + "_rough_cut")
    output_dir.mkdir(parents=True, exist_ok=True)
    total = duration(args.input)
    words = load_words(args.transcript)
    units = split_units(words)
    silences = detect_silences(args.input, output_dir, args.silence_db, args.silence_min)
    deletes = rough_segments(words, units, silences, total)
    out_video = output_dir / f"{args.input.stem}_rough_cut.mp4"
    write_report(output_dir, args.input, out_video, deletes, total)
    if args.render and not args.plan_only:
        render(args.input, out_video, keep_intervals(deletes, total), args.encoder, output_dir)
    print(output_dir)


if __name__ == "__main__":
    main()
