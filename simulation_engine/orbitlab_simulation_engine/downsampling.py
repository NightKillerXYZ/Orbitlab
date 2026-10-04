"""Replaceable deterministic trajectory downsampling."""

from __future__ import annotations

import heapq
import math
from typing import Iterable, Protocol, Sequence, Tuple

from .models import TrajectoryPoint


class TrajectoryDownsampler(Protocol):
    def downsample(
        self,
        points: Sequence[TrajectoryPoint],
        max_points: int,
        landmark_indices: Iterable[int] = (),
    ) -> Tuple[TrajectoryPoint, ...]: ...


class RamerDouglasPeuckerDownsampler:
    """Budgeted three-dimensional RDP that always preserves landmarks."""

    def downsample(
        self,
        points: Sequence[TrajectoryPoint],
        max_points: int,
        landmark_indices: Iterable[int] = (),
    ) -> Tuple[TrajectoryPoint, ...]:
        if max_points < 2:
            raise ValueError("max_points must be at least 2")
        if not points:
            return ()

        landmarks = set(landmark_indices)
        if any(index < 0 or index >= len(points) for index in landmarks):
            raise ValueError("landmark index is outside the trajectory")
        landmarks.update((0, len(points) - 1))
        if len(landmarks) > max_points:
            raise ValueError("max_points is smaller than the number of required landmarks")
        if len(points) <= max_points:
            return tuple(points)

        selected = set(landmarks)
        queue: list[tuple[float, int, int, int]] = []
        anchors = sorted(landmarks)
        for start, end in zip(anchors, anchors[1:]):
            self._queue_segment(points, start, end, queue)

        while queue and len(selected) < max_points:
            negative_distance, index, start, end = heapq.heappop(queue)
            if index in selected or -negative_distance <= 0.0:
                continue
            selected.add(index)
            self._queue_segment(points, start, index, queue)
            self._queue_segment(points, index, end, queue)

        return tuple(points[index] for index in sorted(selected))

    def _queue_segment(
        self,
        points: Sequence[TrajectoryPoint],
        start: int,
        end: int,
        queue: list[tuple[float, int, int, int]],
    ) -> None:
        if end - start <= 1:
            return
        farthest_index = start + 1
        farthest_distance = -1.0
        for index in range(start + 1, end):
            distance = self._point_segment_distance(points[index], points[start], points[end])
            if distance > farthest_distance:
                farthest_distance = distance
                farthest_index = index
        heapq.heappush(queue, (-farthest_distance, farthest_index, start, end))

    @staticmethod
    def _point_segment_distance(
        point: TrajectoryPoint,
        start: TrajectoryPoint,
        end: TrajectoryPoint,
    ) -> float:
        px, py, pz = point.x_km, point.y_km, point.z_km
        ax, ay, az = start.x_km, start.y_km, start.z_km
        bx, by, bz = end.x_km, end.y_km, end.z_km
        abx, aby, abz = bx - ax, by - ay, bz - az
        apx, apy, apz = px - ax, py - ay, pz - az
        length_squared = abx * abx + aby * aby + abz * abz
        if length_squared == 0.0:
            return math.sqrt(apx * apx + apy * apy + apz * apz)
        projection = max(0.0, min(1.0, (apx * abx + apy * aby + apz * abz) / length_squared))
        dx = px - (ax + projection * abx)
        dy = py - (ay + projection * aby)
        dz = pz - (az + projection * abz)
        return math.sqrt(dx * dx + dy * dy + dz * dz)
