#!/usr/bin/env python3
"""Offline pixel verification; Python stdlib + FFmpeg only."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from render_animation import canonical_rgba, segments

ROOT = Path(__file__).resolve().parents[1]
SIZE = 512 * 700 * 4


def decoded(path, decoder=None):
    command = ['ffmpeg', '-v', 'error']
    if decoder:
        command += ['-c:v', decoder]
    command += ['-i', str(path), '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-']
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    frames = []
    first_raw = last_raw = None
    while True:
        frame = process.stdout.read(SIZE)
        if not frame:
            break
        assert len(frame) == SIZE, 'Incomplete decoded frame'
        alpha = frame[3::4]
        # Bilinear integer interpolation can round fully opaque pixels to 254.
        assert min(alpha) == 0 and max(alpha) >= 254, 'Missing alpha'
        assert not any(alpha[:512]) and not any(alpha[-512:]), 'Clipped top/bottom'
        assert not any(alpha[::512]) and not any(alpha[511::512]), 'Clipped side'
        last_raw = hashlib.sha256(frame).digest()
        if first_raw is None:
            first_raw = last_raw
        # RGB under zero alpha is invisible and may differ in source PNG.
        frames.append(hashlib.sha256(canonical_rgba(frame)).hexdigest())
    assert process.wait() == 0
    assert first_raw == last_raw, 'First/last raw RGBA bytes differ'
    return frames


def main():
    curves = segments()
    for start, end, coefficients in curves:
        low, high = sorted((coefficients[0], sum(coefficients)))
        values = [sum(c * (j / 1000)**i for i, c in enumerate(coefficients))
                  for j in range(1001)]
        assert min(values) >= low - 1e-8 and max(values) <= high + 1e-8
    for (a, b, c), (d, e, f) in zip(curves, curves[1:]):
        assert abs(sum(c) - f[0]) < 1e-9
        assert abs(sum(i * v for i, v in enumerate(c)) / (b-a)) < 1e-8
        assert abs(sum(i*(i-1)*v for i, v in enumerate(c)) / (b-a)**2
                   - 2*f[2] / (e-d)**2) < 1e-8
    source = ROOT / 'media/sigmahook-source.png'
    source_hash = decoded(source)[0]
    results = {'motion': {'monotonicBetweenExtrema': True,
                          'angleVelocityAccelerationContinuous': True}}
    for name, decoder in [('artifacts/image-v2.png', None),
                          ('media/sigmahook-pendulum.webm', 'libvpx-vp9')]:
        path = ROOT / name
        probe = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))
        stream = probe['streams'][0]
        assert (stream['width'], stream['height']) == (512, 700)
        assert stream['avg_frame_rate'] == '60/1'
        hashes = decoded(path, decoder)
        assert len(hashes) == 240, (name, len(hashes))
        assert len(set(hashes[:30])) == 1, 'Start hold moved'
        assert len(set(hashes[210:])) == 1, 'End hold moved'
        assert hashes[0] == hashes[-1], 'First and last frames differ'
        assert len(set(hashes[30:210])) > 100, 'Animation is missing'
        if name.endswith('.png'):
            assert hashes[0] == source_hash, 'RGBA master altered source at rest'
            data = path.read_bytes()
            offset = 8
            delays = []
            while offset < len(data):
                length = struct.unpack_from('>I', data, offset)[0]
                if data[offset+4:offset+8] == b'fcTL':
                    delays.append(struct.unpack_from('>HH', data, offset+28))
                offset += length + 12
            assert delays == [(1, 60)] * 240, 'APNG frame delays are not exactly 1/60'
        else:
            assert stream.get('tags', {}).get('alpha_mode') == '1'
            assert abs(float(probe['format']['duration']) - 4) < 0.02
        results[name] = {'frames': len(hashes), 'fps': 60, 'width': 512, 'height': 700,
                         'alpha': True, 'firstLastIdentical': True,
                         'stationaryHolds': True, 'unclipped': True}
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
