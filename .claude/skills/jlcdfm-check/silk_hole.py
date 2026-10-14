"""Gerber とドリルファイルから、シルクと穴の最小距離を穴ごとに出力する。

使い方: python silk_hole.py <gerber ディレクトリ> [しきい値 mm (既定 0.18)]
JLCDFM の Silkscreen to hole と同じ目安で、0.13 mm 未満を Danger、それ以上を Warning とする。
"""
import re
import sys
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

DANGER = 0.13


def find_one(d, pattern):
    hits = [p for p in d.iterdir() if re.search(pattern, p.name, re.IGNORECASE)]
    return hits[0] if hits else None


def silk(path):
    ap, width, segs, scale = {}, 0.0, [], 1e6
    x = y = 0.0
    for line in path.read_text().splitlines():
        m = re.match(r'%FSLAX\d(\d)Y', line)
        if m:
            scale = 10 ** int(m[1])
            continue
        m = re.match(r'%ADD(\d+)C,([\d.]+)', line)
        if m:
            ap[m[1]] = float(m[2])
            continue
        m = re.match(r'(?:G54)?D(\d+)\*$', line)
        if m and m[1] in ap:
            width = ap[m[1]]
            continue
        m = re.match(r'(?:X(-?\d+))?(?:Y(-?\d+))?D0([123])\*', line)
        if m and (m[1] or m[2]):
            nx = int(m[1]) / scale if m[1] else x
            ny = int(m[2]) / scale if m[2] else y
            if m[3] == '1':
                geom = LineString([(x, y), (nx, ny)]) if (x, y) != (nx, ny) else Point(x, y)
                segs.append(geom.buffer(width / 2))
            elif m[3] == '3':
                segs.append(Point(nx, ny).buffer(width / 2))
            x, y = nx, ny
    return unary_union(segs)


def holes(paths):
    out = []
    for path in paths:
        tool, size = None, {}
        for line in path.read_text().splitlines():
            m = re.match(r'T(\d+)C([\d.]+)', line)
            if m:
                size[m[1]] = float(m[2])
                continue
            m = re.match(r'T(\d+)$', line)
            if m:
                tool = m[1]
                continue
            m = re.match(r'X(-?[\d.]+)Y(-?[\d.]+)', line)
            if m and tool in size:
                out.append((float(m[1]), float(m[2]), size[tool]))
    return out


def main():
    d = Path(sys.argv[1])
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else 0.18
    drills = [p for p in (find_one(d, r'-PTH\.drl$'), find_one(d, r'-NPTH\.drl$')) if p]
    hs = holes(drills)
    for side, pattern in (('Top', r'-F_Silkscreen\.gbr$'), ('Bottom', r'-B_Silkscreen\.gbr$')):
        path = find_one(d, pattern)
        if not path:
            continue
        s = silk(path)
        for hx, hy, dia in hs:
            gap = s.distance(Point(hx, hy).buffer(dia / 2))
            if gap < limit:
                level = 'Danger' if gap < DANGER else 'Warning'
                # Gerber の Y は KiCad 座標と符号が逆
                print(f'{side:6} {level:7} hole ø{dia:<6g} ({hx:.2f}, {-hy:.2f})  gap {gap:.3f} mm')


if __name__ == '__main__':
    main()
