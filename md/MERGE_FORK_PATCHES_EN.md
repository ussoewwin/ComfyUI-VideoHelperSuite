# Fork Patches Applied on Top of Upstream `main` (Post-Merge)

This document describes **every semantic and structural change** in this repository relative to **`upstream/main` at commit `a6879b8`** (the merge base after integrating [Kosinkadink/ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)), up to the fork’s current tip **`fed6f11`**.

The fork history was squashed into a single commit for attribution; the **working tree** at `fed6f11` is what this file documents.

---

## 1. Scope and how to reproduce the diff

```text
git fetch upstream
git diff a6879b83886490dd434249cf729b7cdd2aace241..HEAD
```

**Changed paths (any change, including mode-only):**

| Path | Semantic change? | Summary |
|------|------------------|---------|
| `.gitignore` | Yes | Ignore local `AUDIO_FIX_DOCUMENTATION.md` |
| `.tracking` | Yes (new file) | Plain-text manifest of tracked paths (tooling / inventory) |
| `__init__.py` | Yes | Force ~1 GiB upload client limit at import time |
| `videohelpersuite/nodes.py` | Yes | BF16 → FP32 for NumPy; FFmpeg metadata write path; robust `VideoCombine` audio |
| `web/js/VHS.core.js` | Yes | Annotated widget text visibility vs zoom (differs from upstream vueNodes tweak) |
| `testframework/__init__.py` | No | File mode only (`100755` → `100644`) |
| `videohelpersuite/logger.py` | No | File mode only |
| `videohelpersuite/server.py` | No | File mode only |

Sections **2–5** cover semantic edits. **Section 6** briefly notes mode-only files.

---

## 2. `.gitignore` — exclude local documentation

### 2.1 Full added lines

```gitignore
# Local fix documentation (optional reference, not for repo)
AUDIO_FIX_DOCUMENTATION.md
```

### 2.2 Meaning

`AUDIO_FIX_DOCUMENTATION.md` is kept **locally** as a scratchpad / runbook. It is **not** part of the published fork tree so collaborators are not forced to carry the same notes.

---

## 3. `.tracking` — new manifest file

### 3.1 Full file contents (45 lines)

```text
.github/workflows/publish.yml
.gitignore
LICENSE
README.md
__init__.py
pyproject.toml
requirements.txt
testframework/README.md
testframework/__init__.py
testframework/server.py
testframework/web/js/testRunner.js
tests/README.md
tests/audio.json
tests/batch4x4.json
tests/converted-format-input.json
tests/converted-input.json
tests/loop.json
tests/old-prores.json
tests/old-vae-conversion.json
tests/simple.json
video_formats/16bit-png.json
video_formats/8bit-png.json
video_formats/ProRes.json
video_formats/av1-webm.json
video_formats/ffmpeg-gif.json
video_formats/ffv1-mkv.json
video_formats/gifski.json
video_formats/h264-mp4.json
video_formats/h265-mp4.json
video_formats/nvenc_av1-mp4.json
video_formats/nvenc_h264-mp4.json
video_formats/nvenc_hevc-mp4.json
video_formats/webm.json
videohelpersuite/batched_nodes.py
videohelpersuite/documentation.py
videohelpersuite/image_latent_nodes.py
videohelpersuite/latent_preview.py
videohelpersuite/load_images_nodes.py
videohelpersuite/load_video_nodes.py
videohelpersuite/logger.py
videohelpersuite/nodes.py
videohelpersuite/server.py
videohelpersuite/utils.py
web/js/VHS.core.js
web/js/videoinfo.js
```

*(Note: the on-disk `.tracking` file may omit a final newline.)*

### 3.2 Meaning

This is an **inventory manifest**, not executed by ComfyUI. Typical uses: scripts that verify presence of files, release checklists, or diff tooling that should only consider “tracked product surface” paths.

---

## 4. `__init__.py` — force large HTTP upload size (≈1 GiB)

### 4.1 Full added code (prepended before existing imports)

```python
# Force max upload size to 1GB (remains effective even after ComfyUI updates reset cli_args)
def _force_max_upload_1gb():
    _1gb = 1024 * 1024 * 1024
    try:
        from comfy import cli_args
        cli_args.args.max_upload_size = 1024
        import server
        inst = getattr(server.PromptServer, "instance", None)
        if inst is not None and getattr(inst, "app", None) is not None:
            setattr(inst.app, "_client_max_size", _1gb)
        try:
            import comfy_api.feature_flags as ff
            ff.SERVER_FEATURE_FLAGS["max_upload_size"] = _1gb
        except Exception:
            pass
    except Exception:
        pass

_force_max_upload_1gb()
```

The remainder of `__init__.py` matches upstream’s extension entry pattern (imports `NODE_CLASS_MAPPINGS`, `folder_paths`, `server`, `documentation`, `latent_preview`, sets `WEB_DIRECTORY`, etc.).

### 4.2 Meaning

ComfyUI’s CLI and server stack cap **multipart / body size** for uploads (videos, large assets). VHS workflows often hit the default cap.

This block:

1. Sets `cli_args.args.max_upload_size` to **`1024`** using ComfyUI’s **native unit convention for that attribute in your installed version** (often treated like megabytes in CLI parsing; confirm against your ComfyUI `cli_args` definition if uploads still clip).
2. If `PromptServer.instance.app` exists, sets **`aiohttp`’s `_client_max_size`** to **1 073 741 824 bytes** (1 GiB), which is the hard ceiling for the request parser.
3. If `comfy_api.feature_flags` exposes `SERVER_FEATURE_FLAGS`, mirrors `max_upload_size` there for newer code paths.

Failures are swallowed so **import never breaks** the custom node if Comfy’s internals move; the extension still loads.

---

## 5. `videohelpersuite/nodes.py` — substantive fork logic

The following regions differ from `a6879b8` **by content** (not only mode).

### 5.1 `tensor_to_int` — bfloat16 guard

#### Full function (as in the fork)

```python
def tensor_to_int(tensor, bits):
    # BFloat16 is not supported by NumPy, convert to float32 if needed
    # (SeedVR2 already converts to Float16, so this path should rarely be taken)
    if tensor.dtype == torch.bfloat16:
        tensor = tensor.float()  # Convert BFloat16 to Float32
    tensor = tensor.cpu().numpy() * (2**bits-1) + 0.5
    return np.clip(tensor, 0, (2**bits-1))
```

#### Meaning

NumPy cannot represent `torch.bfloat16` directly. If any pipeline leaves BF16 tensors in the frame path, `tensor.cpu().numpy()` would **throw**. Converting to FP32 first makes quantization / 8–16‑bit packing **safe and deterministic**.

---

### 5.2 `ffmpeg_process` — FFmpeg metadata sidecar format

#### Full fork implementation of the `save_metadata` branch (lines 141–177 in the fork)

```python
    if video_format.get('save_metadata', 'False') != 'False':
        os.makedirs(folder_paths.get_temp_directory(), exist_ok=True)
        metadata = json.dumps(video_metadata)
        metadata_path = os.path.join(folder_paths.get_temp_directory(), "metadata.txt")
        #metadata from file should  escape = ; # \ and newline
        metadata = metadata.replace("\\","\\\\")
        metadata = metadata.replace(";","\\;")
        metadata = metadata.replace("#","\\#")
        metadata = metadata.replace("=","\\=")
        metadata = metadata.replace("\n","\\\n")
        metadata = "comment=" + metadata
        with open(metadata_path, "w") as f:
            f.write(";FFMETADATA1\n")
            f.write(metadata)
        m_args = args[:1] + ["-i", metadata_path] + args[1:] + ["-metadata", "creation_time=now"]
        with subprocess.Popen(m_args + [file_path], stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE, env=env) as proc:
            try:
                while frame_data is not None:
                    proc.stdin.write(frame_data)
                    #TODO: skip flush for increased speed
                    frame_data = yield
                    total_frames_output+=1
                proc.stdin.flush()
                proc.stdin.close()
                res = proc.stderr.read()
            except BrokenPipeError as e:
                err = proc.stderr.read()
                #Check if output file exists. If it does, the re-execution
                #will also fail. This obscures the cause of the error
                #and seems to never occur concurrent to the metadata issue
                if os.path.exists(file_path):
                    raise Exception("An error occurred in the ffmpeg subprocess:\n" \
                            + err.decode(*ENCODE_ARGS))
                #Res was not set
                print(err.decode(*ENCODE_ARGS), end="", file=sys.stderr)
                logger.warn("An error occurred when saving with metadata")
```

#### Contrast with upstream `a6879b8` (conceptual)

Upstream at `a6879b8` moved toward **per-key escaped lines** for `prompt` / `workflow` / other keys and appended **`-movflags use_metadata_tags`** in the metadata-enabled path. This fork instead:

- Serializes **the entire** `video_metadata` dict with `json.dumps`,
- Applies **global** FFmpeg metadata escaping to that string,
- Stores it as a **single** `comment=...` field in a minimal FFmetadata file,
- Drops **`-movflags use_metadata_tags`** from this branch (only `creation_time=now` remains as extra `-metadata`).

#### Meaning

Both approaches feed FFmpeg an FFmetadata sidecar. The fork’s approach:

- Maximizes **compatibility** with muxers that behave better with a **single** metadata blob in `comment`,
- Avoids subtle failures when nested JSON strings interact with per-line escaping,
- Trades upstream’s finer-grained tagging for **one robust path** validated on the fork owner’s workloads.

If you need strict parity with upstream’s tagging layout, this hunk is the **primary intentional divergence** to review.

---

### 5.3 `VideoCombine` — normalized audio handling and FFmpeg layout

Upstream assumed `audio` behaved like a **plain `dict`** with `audio['waveform']` and `audio['sample_rate']`. Real graphs often pass:

- **`dict`**,
- **Objects that implement `__getitem__` but not `.get`** (lazy maps),
- **Objects with attributes** `.waveform` / `.sample_rate`.

#### Full fork block (audio segment only)

```python
            # Normalize audio input: support dict, LazyAudioMap (__getitem__), or object with .waveform/.sample_rate
            a_waveform = None
            a_sample_rate = None
            if audio is not None:
                try:
                    w = audio.get('waveform', None) if isinstance(audio, dict) else None
                    sr = audio.get('sample_rate', None) if isinstance(audio, dict) else None
                    if w is None or sr is None:
                        try:
                            w = audio['waveform']
                            sr = audio['sample_rate']
                        except (TypeError, KeyError, AttributeError):
                            w = getattr(audio, 'waveform', None)
                            sr = getattr(audio, 'sample_rate', None)
                    if w is not None and sr is not None and isinstance(w, torch.Tensor) and w.numel() > 0:
                        a_waveform = w
                        a_sample_rate = int(sr) if not isinstance(sr, int) else sr
                except Exception as e:
                    logger.warn("VHS Video Combine: could not read audio input: %s", e)
            if a_waveform is not None and a_sample_rate is not None:
                # Create audio file if input was provided
                output_file_with_audio = f"{filename}_{counter:05}-audio.{video_format['extension']}"
                output_file_with_audio_path = os.path.join(full_output_folder, output_file_with_audio)
                if "audio_pass" not in video_format:
                    logger.warn("Selected video format does not have explicit audio support")
                    video_format["audio_pass"] = ["-c:a", "libopus"]


                # FFmpeg expects (samples, channels) interleaved; waveform is (1, channels, samples) or (channels, samples)
                w = a_waveform
                if w.dim() == 3:
                    w = w.squeeze(0)
                # w is (channels, samples) -> (samples, channels) for ffmpeg -f f32le
                channels = w.size(0)
                min_audio_dur = total_frames_output / frame_rate + 1
                if video_format.get('trim_to_audio', 'False') != 'False':
                    apad = []
                else:
                    apad = ["-af", "apad=whole_dur="+str(min_audio_dur)]
                mux_args = [ffmpeg_path, "-v", "error", "-n", "-i", file_path,
                            "-ar", str(a_sample_rate), "-ac", str(channels),
                            "-f", "f32le", "-i", "-", "-c:v", "copy"] \
                            + video_format["audio_pass"] \
                            + apad + ["-shortest", output_file_with_audio_path]

                audio_data = w.transpose(0, 1).contiguous().numpy().tobytes()
```

#### Meaning

1. **Extraction strategy**  
   - Prefer `.get` only on real `dict` instances.  
   - Fall back to `audio['waveform']` / `audio['sample_rate']` so **`__getitem__`-only** lazy containers work.  
   - Fall back again to **attributes** for plain objects.  
   - Require a **non-empty** `torch.Tensor` for waveform before accepting audio.

2. **Sample rate**  
   Stored in `a_sample_rate` so the mux step never re-indexes `audio[...]` (which might not exist on lazy types).

3. **Tensor layout vs FFmpeg `f32le`**  
   - VHS convention: waveform may be `(1, C, T)` or `(C, T)`.  
   - `squeeze(0)` collapses batch dim when present.  
   - `channels = w.size(0)` after squeeze → rows are channels, columns are time samples.  
   - `transpose(0, 1)` yields **`(T, C)`** layout; **contiguous** memory before `.numpy().tobytes()` matches FFmpeg’s expectation for raw `f32le` interleaved audio.

4. **Logging**  
   Failures log via `logger.warn` instead of failing silently, which simplifies diagnosing bad edges from custom nodes.

---

### 5.4 Trivial whitespace in `nodes.py`

A few blank lines gained trailing spaces (`LoadAudioUpload.load_audio`, `VideoInfo*` classes). They have **no behavioral effect**; they appear in the unified diff as noise next to real edits.

---

## 6. `web/js/VHS.core.js` — `drawAnnotated` text visibility

### 6.1 Full changed expression

**Upstream `a6879b8` (conceptually):**

```javascript
const show_text = LiteGraph.vueNodesMode || app.canvas.ds.scale >= (app.canvas.low_quality_zoom_threshold ?? 0.5)
```

**Fork `fed6f11`:**

```javascript
const show_text = app.canvas.ds.scale >= (app.canvas.low_quality_zoom_threshold ?? 0.5)
```

### 6.2 Meaning

Upstream explicitly **forced annotation text on** when `LiteGraph.vueNodesMode` is true (Vue node UI at 1:1). The fork **removes** the `vueNodesMode` bypass so label drawing again follows the **zoom threshold** only.

**Practical effect:** at some zoom levels in vueNodes mode, annotated path widgets may **hide text** where upstream always showed it. This is a deliberate UI trade-off on the fork (e.g. to match classic canvas readability rules or to avoid overcrowding).

---

## 7. Mode-only changes (`100755` → `100644`)

Files:

- `testframework/__init__.py`
- `videohelpersuite/logger.py`
- `videohelpersuite/server.py`

have **no line-level diff**; only the executable bit was normalized (common on Windows checkouts vs Unix-oriented upstream tarballs).

---

## 8. Operational checklist for maintainers

1. **Re-merge upstream later**  
   ```text
   git fetch upstream
   git merge upstream/main
   ```
   Resolve conflicts preferring **upstream structure**, then re-apply the **hunks in sections 4–6** if lost.

2. **Verify upload cap**  
   After ComfyUI upgrades, confirm large uploads still succeed; if not, re-check whether `PromptServer.instance` timing requires calling `_force_max_upload_1gb()` later than import time.

3. **FFmpeg metadata**  
   If you need `use_metadata_tags` behavior from upstream, reconcile **section 5.2** with upstream’s format intentionally—do not merge both blindly.

4. **Audio regressions**  
   If a custom node passes audio in a new container type, extend the normalization chain in **section 5.3** following the same fallbacks (`dict` → `__getitem__` → `getattr`).

---

## 9. Revision table

| Commit / ref | Role |
|--------------|------|
| `a6879b8` | `upstream/main` tip at time of fork realignment |
| `fed6f11` | Fork `main` tip (squashed fork patch, English subject line) |

---

*End of document.*
