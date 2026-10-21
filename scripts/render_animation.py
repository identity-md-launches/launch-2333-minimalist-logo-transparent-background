#!/usr/bin/env python3
"""Render the unchanged SigmaHook logo. Requires Python 3 and FFmpeg with libvpx.

No Python packages or network access are needed.
"""
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
FPS = 60
FRAMES = 240
PIVOT = (211, 181)  # Rounded left tip of the silver hook, in source pixels.
# Positive is a rightward swing of the suspended medallion.
KNOTS = [(0.5, 0), (0.75, 8), (1.25, -8), (1.75, 5),
         (2.25, -5), (2.75, 2), (3.25, -2), (3.5, 0)]


def segments():
    """Quintic Hermite curves: continuous angle, velocity and acceleration.

    Extremes have zero velocity and harmonic restoring acceleration. At the
    initial release and final rest both velocity and acceleration are zero.
    """
    result = []
    for (start, a), (end, b) in zip(KNOTS, KNOTS[1:]):
        duration = end - start
        c0 = a
        c1 = 0
        c2 = -((2 * math.pi) ** 2) * a * duration**2 / 2
        finish_accel = -((2 * math.pi) ** 2) * b * duration**2
        delta = b - c0 - c2
        velocity = -2 * c2
        accel = finish_accel - 2 * c2
        c3 = 10 * delta - 4 * velocity + accel / 2
        c4 = -15 * delta + 7 * velocity - accel
        c5 = 6 * delta - 3 * velocity + accel / 2
        result.append((start, end, [c0, c1, c2, c3, c4, c5]))
    return result


def angle_at(t):
    for start, end, coefficients in segments():
        if start <= t < end:
            u = (t - start) / (end - start)
            return sum(c * u**i for i, c in enumerate(coefficients))
    return 0.0


def angle_expression():
    expr = '0'
    for start, end, coefficients in reversed(segments()):
        u = f'((t-{start})/{end-start})'
        poly = '+'.join(f'({c:.16g})*pow({u},{i})'
                        for i, c in enumerate(coefficients) if c)
        expr = f'if(lt(t,{end}),({poly}),{expr})'
    # FFmpeg's clockwise-positive convention is opposite to our rightward swing.
    return f'if(lt(t,0.5),0,-PI/180*({expr}))'


def run(args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args],
                   check=True)


def exact_apng_timing(path):
    """Use APNG's exact rational 1/60 rather than FFmpeg's rounded timebase."""
    source = path.read_bytes()
    output = bytearray(source[:8])
    offset = 8
    while offset < len(source):
        length = struct.unpack_from('>I', source, offset)[0]
        kind = source[offset + 4:offset + 8]
        data = source[offset + 8:offset + 8 + length]
        if kind == b'fcTL':
            data = data[:20] + struct.pack('>HH', 1, FPS) + data[24:]
        output += struct.pack('>I', length) + kind + data
        output += struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        offset += 12 + length
    path.write_bytes(output)


def canonical_rgba(frame):
    """Clear invisible RGB so frame-difference encoding cannot retain old color."""
    data = bytearray(frame)
    for pixel, alpha in enumerate(data[3::4]):
        if alpha == 0:
            i = pixel * 4
            data[i:i+3] = b'\x00\x00\x00'
    return data


def main():
    media = ROOT / 'media'
    source = media / 'sigmahook-source.png'
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    master = ROOT / 'artifacts/image-v2.png'
    # Place the selected pivot at the exact center of an even 1400px canvas.
    # Crop back after rotation; nothing is scaled or translated in the result.
    x, y = 700 - PIVOT[0], 700 - PIVOT[1]
    vf = (f'format=rgba,pad=1400:1400:{x}:{y}:color=0x00000000,'
          f"rotate=angle='{angle_expression()}':ow=iw:oh=ih:c=none,"
          f'crop=512:700:{x}:{y},format=rgba')
    with tempfile.TemporaryDirectory(prefix='sigmahook-') as tmp:
        filt = Path(tmp) / 'rotation.txt'
        filt.write_text(vf)
        renderer = subprocess.Popen([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-loop', '1',
            '-framerate', str(FPS), '-i', str(source), '-filter_script:v', str(filt),
            '-frames:v', str(FRAMES), '-threads', '2', '-f', 'rawvideo',
            '-pix_fmt', 'rgba', '-'], stdout=subprocess.PIPE)
        encoder = subprocess.Popen([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
            '-pix_fmt', 'rgba', '-video_size', '512x700', '-framerate', str(FPS),
            '-i', '-', '-threads', '2', '-c:v', 'apng', '-plays', '0',
            '-f', 'apng', str(master)], stdin=subprocess.PIPE)
        try:
            for _ in range(FRAMES):
                frame = renderer.stdout.read(512 * 700 * 4)
                if len(frame) != 512 * 700 * 4:
                    raise RuntimeError('Renderer returned an incomplete frame')
                encoder.stdin.write(canonical_rgba(frame))
        finally:
            renderer.stdout.close()
            encoder.stdin.close()
        if renderer.wait() or encoder.wait():
            raise RuntimeError('Animation render failed')
    exact_apng_timing(master)
    # APNG is the full RGBA master; VP9 has the standard 4:2:0 chroma conversion.
    run(['-ignore_loop', '1', '-i', str(master),
         '-an', '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-lossless', '1',
         '-auto-alt-ref', '0', '-row-mt', '1', '-threads', '2',
         '-r', str(FPS), '-frames:v', str(FRAMES),
         str(media / 'sigmahook-pendulum.webm')])
    record = {
        'output': 'artifacts/image-v2.png', 'format': 'image/png',
        'dimensions': {'width': 512, 'height': 700}, 'colorMode': 'RGBA',
        'animated': True, 'frames': FRAMES, 'fps': FPS, 'durationSeconds': 4,
        'animation': {'output': 'media/sigmahook-pendulum.webm',
                      'format': 'video/webm; codecs=vp9', 'alpha': True,
                      'width': 512, 'height': 700, 'fps': FPS,
                      'frames': FRAMES, 'durationSeconds': 4,
                      'losslessRgbaMaster': 'artifacts/image-v2.png',
                      'pivotPixels': list(PIVOT),
                      'extremaDegreesRightPositive': KNOTS,
                      'startHoldSeconds': 0.5, 'endHoldSeconds': 0.5},
        'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'unmetVisualRequirements': [],
        'limitations': [
            'The named PNG is APNG; PNG viewers without animation support show its first frame.',
            'VP9 uses 4:2:0 chroma; APNG preserves full RGBA color.',
            'WebM alpha requires browser support; preview offers APNG fallback.',
            'Motion is a C2 continuous damped pendulum approximation with a smooth release and settling, not a physical simulation.'
        ]
    }
    (ROOT / 'image-result.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
