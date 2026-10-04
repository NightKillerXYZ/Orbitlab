import math
import unittest

from orbitlab_simulation_engine import RamerDouglasPeuckerDownsampler, TrajectoryPoint


def point(index: int, *, spike: bool = False) -> TrajectoryPoint:
    angle = index / 100.0
    radius = 7000.0 + (1000.0 if spike else 0.0)
    return TrajectoryPoint(
        elapsed_secs=float(index),
        x_km=radius * math.cos(angle),
        y_km=radius * math.sin(angle),
        z_km=float(index % 11),
        vx_km_s=0.0,
        vy_km_s=7.5,
        vz_km_s=0.0,
        semi_major_axis_km=7000.0,
        eccentricity=0.001,
        inclination_deg=28.5,
        altitude_km=621.864,
    )


class TestTrajectoryDownsampling(unittest.TestCase):
    def setUp(self):
        self.downsampler = RamerDouglasPeuckerDownsampler()

    def test_is_deterministic_and_respects_visualization_limit(self):
        points = tuple(point(index) for index in range(5000))

        first = self.downsampler.downsample(points, 2000)
        second = self.downsampler.downsample(points, 2000)

        self.assertLessEqual(len(first), 2000)
        self.assertEqual(first, second)
        self.assertEqual(first[0], points[0])
        self.assertEqual(first[-1], points[-1])
        self.assertEqual(len(points), 5000)

    def test_preserves_event_landmarks(self):
        points = tuple(point(index, spike=index == 1234) for index in range(3000))

        sampled = self.downsampler.downsample(points, 100, landmark_indices=(1234, 2000))

        self.assertIn(points[1234], sampled)
        self.assertIn(points[2000], sampled)
        self.assertLessEqual(len(sampled), 100)

    def test_rejects_landmark_budget_and_invalid_index(self):
        points = tuple(point(index) for index in range(10))
        with self.assertRaisesRegex(ValueError, "required landmarks"):
            self.downsampler.downsample(points, 2, landmark_indices=(2, 4))
        with self.assertRaisesRegex(ValueError, "outside"):
            self.downsampler.downsample(points, 5, landmark_indices=(99,))
