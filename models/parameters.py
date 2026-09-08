from dataclasses import dataclass


@dataclass(frozen=True)
class PlanterConfig:
    """All dimensions are millimetres."""

    length: float = 1500.0
    depth: float = 450.0
    body_height: float = 500.0

    frame_size: float = 30.0
    frame_wall: float = 2.0

    trellis_height: float = 2000.0
    trellis_post_size: float = 40.0
    trellis_post_wall: float = 2.0
    trellis_gap: float = 10.0

    slat_width: float = 45.0
    slat_thickness: float = 20.0
    slat_gap: float = 15.0
    slat_bottom_clearance: float = 40.0
    slat_top_clearance: float = 40.0

    @property
    def slat_height(self) -> float:
        return self.body_height - self.slat_bottom_clearance - self.slat_top_clearance
