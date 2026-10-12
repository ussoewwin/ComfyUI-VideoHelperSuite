# Changelog

## [1.2.0] — 2026-10-12

**v1.2 (fork):** Merged official upstream `main` (`4d907be`) while fully preserving fork patches (1GB upload limit, BF16 NumPy guard, ffmpeg metadata comment escaping, robust audio handling, and widget zoom threshold). Incorporates upstream H3 format support, IO.ComfyNode Unbatch updates, and frontend stability fixes.

## [1.1.0] — 2026-05-13

**v1.1 (fork):** Merged **upstream `main`** with v1.0 fixes kept; **README** defers to the official README; **docs** under `md/` (this file + [`MERGE_FORK_PATCHES_EN.md`](MERGE_FORK_PATCHES_EN.md)). Extra vs v1.0-only story: **BF16 guard** in `tensor_to_int`, **FFmpeg metadata** sidecar fork variant, **`drawAnnotated`** text gated by zoom only.

## [1.0.0] — 2026-05-13

**v1.0 (fork):** Video Helper Suite only — **Video Combine** gets reliable muxed audio (dict / LazyAudioMap / attributes, correct `f32le` layout) and **~1 GB** upload behavior at runtime, **without editing ComfyUI core**. Details: [`AUDIO_FIX_DOCUMENTATION.md`](AUDIO_FIX_DOCUMENTATION.md).
