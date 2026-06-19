from __future__ import annotations

import math
from typing import Iterable


def bbox_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def point_bbox(lng: float, lat: float) -> tuple[float, float, float, float]:
    return lng, lat, lng, lat


def geometry_bbox(geometry: dict | None) -> tuple[float, float, float, float] | None:
    if not geometry:
        return None
    min_lng = float("inf")
    min_lat = float("inf")
    max_lng = float("-inf")
    max_lat = float("-inf")

    def walk(obj):
        nonlocal min_lng, min_lat, max_lng, max_lat
        if isinstance(obj, (list, tuple)) and obj and isinstance(obj[0], (int, float)):
            lng = float(obj[0])
            lat = float(obj[1])
            min_lng = min(min_lng, lng)
            min_lat = min(min_lat, lat)
            max_lng = max(max_lng, lng)
            max_lat = max(max_lat, lat)
            return
        if isinstance(obj, (list, tuple)):
            for item in obj:
                walk(item)

    walk(geometry.get("coordinates", []))
    if min_lng == float("inf"):
        return None
    return min_lng, min_lat, max_lng, max_lat


def metres_to_degree_buffer(metres: float) -> float:
    return metres / 111_320.0


def point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)


def point_in_ring(lng: float, lat: float, ring: Iterable[Iterable[float]]) -> bool:
    inside = False
    points = list(ring)
    if len(points) < 3:
        return False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = float(points[i][0]), float(points[i][1])
        xj, yj = float(points[j][0]), float(points[j][1])
        intersects = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def point_in_polygon(lng: float, lat: float, polygon_coords: list[list[list[float]]]) -> bool:
    if not polygon_coords:
        return False
    outer = polygon_coords[0]
    if not point_in_ring(lng, lat, outer):
        return False
    for hole in polygon_coords[1:]:
        if point_in_ring(lng, lat, hole):
            return False
    return True


def point_in_geometry(lng: float, lat: float, geometry: dict | None) -> bool:
    if not geometry:
        return False
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        return point_in_polygon(lng, lat, coords)
    if gtype == "MultiPolygon":
        return any(point_in_polygon(lng, lat, polygon) for polygon in coords)
    return False


def iter_polygon_rings(geometry: dict | None):
    if not geometry:
        return
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        for ring in coords:
            yield ring
    elif gtype == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                yield ring


def point_to_geometry_distance_metres(lng: float, lat: float, geometry: dict | None) -> float:
    if not geometry:
        return float("inf")
    if point_in_geometry(lng, lat, geometry):
        return 0.0
    min_deg = float("inf")
    for ring in iter_polygon_rings(geometry):
        for i in range(1, len(ring)):
            ax, ay = ring[i - 1]
            bx, by = ring[i]
            min_deg = min(min_deg, point_segment_distance(lng, lat, ax, ay, bx, by))
    if math.isinf(min_deg):
        return float("inf")
    return min_deg * 111_320.0


def ring_segments(ring: list[list[float]]):
    for i in range(1, len(ring)):
        yield ring[i - 1], ring[i]


def segment_intersects_segment(a1, a2, b1, b2) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p, q, r):
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)

    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True
    if o1 == 0 and on_segment(a1, b1, a2):
        return True
    if o2 == 0 and on_segment(a1, b2, a2):
        return True
    if o3 == 0 and on_segment(b1, a1, b2):
        return True
    if o4 == 0 and on_segment(b1, a2, b2):
        return True
    return False


def geometry_intersects_geometry(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    bbox_a = geometry_bbox(a)
    bbox_b = geometry_bbox(b)
    if bbox_a is None or bbox_b is None or not bbox_intersects(bbox_a, bbox_b):
        return False

    def polygons(geometry: dict):
        gtype = geometry.get("type")
        coords = geometry.get("coordinates")
        if gtype == "Polygon":
            yield coords
        elif gtype == "MultiPolygon":
            for polygon in coords:
                yield polygon

    # vertex-in-polygon checks
    for polygon in polygons(a):
        outer = polygon[0]
        for pt in outer:
            if point_in_geometry(pt[0], pt[1], b):
                return True
    for polygon in polygons(b):
        outer = polygon[0]
        for pt in outer:
            if point_in_geometry(pt[0], pt[1], a):
                return True

    # segment intersection checks
    segs_a = []
    segs_b = []
    for polygon in polygons(a):
        for ring in polygon:
            segs_a.extend(list(ring_segments(ring)))
    for polygon in polygons(b):
        for ring in polygon:
            segs_b.extend(list(ring_segments(ring)))
    for sa1, sa2 in segs_a:
        for sb1, sb2 in segs_b:
            if segment_intersects_segment(sa1, sa2, sb1, sb2):
                return True
    return False
