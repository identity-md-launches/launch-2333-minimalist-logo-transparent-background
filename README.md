# SigmaHook pendulum

The original silver hook, silver string and gold sigma medallion rotate together around the rounded left tip of the hook at source pixel **(211, 181)**. The design, scale and proportions are preserved.

Delivered files:

- `media/sigmahook-pendulum.webm` — **512 × 700, 60 fps, 240 frames, 4 seconds**, VP9 with alpha.
- `artifacts/image-v2.png` — required transparent animated PNG (APNG), full RGBA animation master with infinite looping. This named output is uploaded separately.
- `media/sigmahook-source.png` — original unmodified logo, retained for offline reproduction.
- `image-result.json` — machine-readable output properties and limitations.

Open `preview.html` to play and review the animation on a checkerboard or **#0A0C10** background. Click **Replay from rest** to inspect the full sequence. Visual approval should check the pivot, decreasing swings, smooth turns, still holds and transparent edges; structural checks cannot certify aesthetic approval.

## Motion

The first 0.5 seconds are perfectly still. Rightward extrema occur at 0.75s (+8°), 1.75s (+5°), and 2.75s (+2°); leftward extrema at 1.25s (−8°), 2.25s (−5°), and 3.25s (−2°). The logo returns to rest at 3.5s and remains still through the end. Each turning point has zero velocity with continuous restoring acceleration, giving deceleration rather than an artificial pause. The motion is a smooth pendulum approximation with a gentle initial release and final settling. It is not an unforced physics simulation: a real object initially at rest needs energy to begin swinging.

## Reproduce and check offline

Requires Python 3 and FFmpeg/FFprobe with APNG and libvpx-vp9 support. No Python packages, downloaded dependencies or network access are needed.

```sh
python3 scripts/render_animation.py
python3 scripts/verify_animation.py
```

The checker decodes every frame, verifies dimensions, rate, frame count, transparency, stationary holds, unclipped alpha bounds, and identical first/last decoded frames. It also checks that the APNG at rest matches the original visible RGBA pixels exactly; invisible RGB under zero alpha is cleared for consistent encoding.

## Limitations

The named PNG contains APNG animation; viewers without APNG support show the centered first frame. WebM alpha depends on player support; the preview offers APNG as a fallback. VP9 uses standard 4:2:0 chroma conversion, so the APNG master is provided to preserve full RGBA color. Rotated frames require interpolation, but there is no redrawing, recoloring, scaling, or independent movement of logo components.

The APNG master is stored only at the separately uploaded `artifacts/image-v2.png` path to avoid duplicating the large export in the source bundle. Place that downloaded export at this path to use the local preview or verifier; the offline renderer can also recreate it. The source bundle retains the WebM animation and original logo.
