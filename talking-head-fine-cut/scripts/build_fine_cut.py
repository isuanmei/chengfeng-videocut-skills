#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PUNCT_RE = re.compile(r"[\s，。！？、,.!?；;：:“”\"'（）()\[\]{}《》<>~·…—\-_]+")
FILLER_CHARS = {"嗯", "啊", "呃", "额", "欸", "诶", "哎"}
LEADING_FILLERS = ("那个", "这个", "就是", "然后", "那么", "其实", "所以", "好", "对吧")
REFERENTIAL_HINTS = ("工具", "案例", "按钮", "画面", "视频", "声音", "音乐", "效果", "节点", "文件", "素材", "地方")


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Char:
    text: str
    start: float
    end: float


@dataclass
class Unit:
    text: str
    norm: str
    start: float
    end: float
    char_start: int
    char_end: int


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
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path], capture=True).strip())


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


def words_to_chars(words: list[Word]) -> list[Char]:
    chars: list[Char] = []
    for word in words:
        useful = [ch for ch in word.text if norm(ch)]
        if not useful:
            continue
        span = max(0.02, word.end - word.start)
        step = span / len(useful)
        cursor = word.start
        for ch in useful:
            chars.append(Char(ch, cursor, cursor + step))
            cursor += step
    return chars


def split_units(chars: list[Char], gap: float = 0.48, max_chars: int = 36) -> list[Unit]:
    if not chars:
        return []
    units: list[Unit] = []
    start = 0
    for idx in range(len(chars) - 1):
        if chars[idx + 1].start - chars[idx].end >= gap or idx - start + 1 >= max_chars:
            text = "".join(ch.text for ch in chars[start : idx + 1])
            normalized = norm(text)
            if normalized:
                units.append(Unit(text, normalized, chars[start].start, chars[idx].end, start, idx))
            start = idx + 1
    text = "".join(ch.text for ch in chars[start:])
    normalized = norm(text)
    if normalized:
        units.append(Unit(text, normalized, chars[start].start, chars[-1].end, start, len(chars) - 1))
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
    text = run(["ffmpeg", "-hide_banner", "-i", video, "-af", f"silencedetect=n={db}:d={min_dur}", "-f", "null", "-"], capture=True)
    (output_dir / "silencedetect.log").write_text(text, encoding="utf-8")
    silences = parse_silences(text)
    (output_dir / "silences.json").write_text(json.dumps(silences, ensure_ascii=False, indent=2), encoding="utf-8")
    return silences


def add(segments: list[dict], start: float, end: float, reason: str, text: str = "", review: bool = False) -> None:
    if end - start >= 0.06:
        segments.append({"start": max(0.0, start), "end": max(0.0, end), "reason": reason, "text": text, "review": review})


def load_base(path: Path | None) -> list[dict]:
    if not path:
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def style_params(style: str) -> dict:
    if style == "tight":
        return {"silence_threshold": 0.55, "pad_short": 0.22, "pad_long": 0.30, "leading_min_tail": 3}
    return {"silence_threshold": 0.68, "pad_short": 0.26, "pad_long": 0.36, "leading_min_tail": 5}


def lcp(a: str, b: str) -> int:
    count = 0
    for left, right in zip(a, b):
        if left != right:
            break
        count += 1
    return count


def fine_segments(chars: list[Char], units: list[Unit], silences: list[dict], total: float, style: str) -> list[dict]:
    params = style_params(style)
    segments: list[dict] = []
    for silence in silences:
        start, end = float(silence["start"]), float(silence["end"])
        dur = end - start
        if start <= 0.2:
            add(segments, 0.0, max(0.0, end - 0.14), "fine: trim leading silence")
        elif total - end <= 0.25:
            add(segments, min(total, start + 0.14), total, "fine: trim trailing silence")
        elif dur >= params["silence_threshold"]:
            pad = params["pad_long"] if dur >= 2.0 else params["pad_short"]
            add(segments, start + pad, end - pad, f"fine: tighten silence {dur:.2f}s")

    for idx, ch in enumerate(chars):
        if ch.text not in FILLER_CHARS:
            continue
        prev_gap = 999.0 if idx == 0 else ch.start - chars[idx - 1].end
        next_gap = 999.0 if idx == len(chars) - 1 else chars[idx + 1].start - ch.end
        if prev_gap >= 0.08 or next_gap >= 0.08:
            start = chars[idx - 1].end if idx > 0 and prev_gap < 0.18 else ch.start
            end = chars[idx + 1].start if idx + 1 < len(chars) and next_gap < 0.18 else ch.end
            add(segments, start, end, "fine: remove standalone filler syllable", ch.text)

    full_text = "".join(ch.text for ch in chars)
    for phrase in ["嗯", "啊", "呃", "那个", "这个", "就是", "然后"]:
        doubled = phrase + phrase
        for match in re.finditer(re.escape(doubled), full_text):
            add(segments, chars[match.start()].start, chars[match.start() + len(phrase) - 1].end, "fine: remove repeated filler cluster", phrase)

    for unit in units:
        if unit.norm in FILLER_CHARS and unit.end - unit.start <= 1.4:
            add(segments, unit.start, unit.end, "fine: remove filler-only unit", unit.text)
            continue
        for filler in LEADING_FILLERS:
            if not unit.norm.startswith(filler):
                continue
            tail = unit.norm[len(filler) :]
            if len(tail) < params["leading_min_tail"]:
                continue
            end_idx = min(unit.char_start + len(filler) - 1, unit.char_end)
            review = filler in {"那个", "这个"} and any(tail.startswith(hint) for hint in REFERENTIAL_HINTS)
            add(segments, chars[unit.char_start].start, chars[end_idx].end, "fine: remove sentence-leading filler word", filler, review)
            break

    for idx in range(len(units) - 1):
        curr, nxt = units[idx], units[idx + 1]
        common = lcp(curr.norm, nxt.norm)
        if common >= 5:
            victim = curr if len(curr.norm) <= len(nxt.norm) + 4 else nxt
            add(segments, victim.start, victim.end, "fine: remove repeated start", victim.text)
        if len(curr.norm) <= 10 and common >= max(3, len(curr.norm) - 1):
            add(segments, curr.start, curr.end, "fine: remove abandoned start before cleaner retake", curr.text)
    return segments


def merge(segments: list[dict], total: float) -> list[dict]:
    cleaned = []
    for seg in segments:
        start = max(0.0, min(total, float(seg["start"])))
        end = max(0.0, min(total, float(seg["end"])))
        if end - start >= 0.06:
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
        merged[-1]["review"] = bool(merged[-1].get("review")) or bool(seg.get("review"))
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
    delete_duration = sum(d["end"] - d["start"] for d in deletes)
    payload = {"source": str(video), "output": str(out_video), "source_duration": total, "delete_count": len(deletes), "delete_duration": delete_duration, "deletes": deletes, "keep": keep}
    (output_dir / "fine_delete_segments.json").write_text(json.dumps(deletes, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "fine_cut_plan.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Fine Cut Report", "", f"- Source: `{video}`", f"- Output: `{out_video}`", f"- Source duration: {total:.2f}s", f"- Delete count: {len(deletes)}", f"- Delete duration: {delete_duration:.2f}s", f"- Estimated output: {total - delete_duration:.2f}s", "", "| start | end | duration | review | reason | text |", "|---:|---:|---:|---|---|---|"]
    for seg in deletes:
        lines.append(f"| {seg['start']:.2f} | {seg['end']:.2f} | {seg['end'] - seg['start']:.2f} | {str(bool(seg.get('review'))).lower()} | {seg['reason']} | {str(seg.get('text', '')).replace('|', '/')[:80]} |")
    (output_dir / "fine_cut_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    parser.add_argument("--base-delete", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--style", choices=["normal", "tight"], default="tight")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--encoder", choices=["auto", "x264", "videotoolbox"], default="auto")
    parser.add_argument("--silence-db", default="-35dB")
    parser.add_argument("--silence-min", type=float, default=0.45)
    args = parser.parse_args()

    output_dir = args.output_dir or args.input.with_suffix("").with_name(args.input.stem + "_fine_cut")
    output_dir.mkdir(parents=True, exist_ok=True)
    total = duration(args.input)
    words = load_words(args.transcript)
    chars = words_to_chars(words)
    units = split_units(chars)
    silences = detect_silences(args.input, output_dir, args.silence_db, args.silence_min)
    deletes = merge(load_base(args.base_delete) + fine_segments(chars, units, silences, total, args.style), total)
    out_video = output_dir / f"{args.input.stem}_fine_cut.mp4"
    write_report(output_dir, args.input, out_video, deletes, total)
    if args.render and not args.plan_only:
        render(args.input, out_video, keep_intervals(deletes, total), args.encoder, output_dir)
    print(output_dir)


if __name__ == "__main__":
    main()
