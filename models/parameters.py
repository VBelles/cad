from dataclasses import dataclass


@dataclass(frozen=True)
class PlanterConfig:
    """Fabrication dimensions in millimetres unless stated otherwise."""

    # Finished envelope, including the four continuous 40x40 steel uprights/legs.
    length: float = 600.0
    depth: float = 600.0
    body_height: float = 600.0

    # Main welded frame: Obramat raw steel tube 40x40x1.5 mm.
    frame_size: float = 40.0
    frame_wall: float = 1.5
    leg_clearance: float = 80.0

    # Internal load platform: Obramat steel tube 20x20x1.5 mm.
    support_size: float = 20.0
    support_wall: float = 1.5
    bag_support_z: float = 120.0

    # Removable bag frame, supported just inside the 40 mm top border.
    bag_frame_outer: float = 500.0
    bag_frame_z: float = 563.0
    bag_wall: float = 2.0

    # Obramat steel angle 20x20x3 mm.
    angle_leg: float = 20.0
    angle_wall: float = 3.0
    bag_ledge_length: float = 100.0

    # Removable drain tray under the lower frame, between the legs.
    tray_width: float = 510.0
    tray_depth: float = 500.0
    tray_z: float = 48.0
    tray_wall_height: float = 10.0
    tray_sheet: float = 1.0
    drain_nominal_diameter: float = 20.0
    drain_local_x: float = 400.0
    drain_local_y: float = 450.0

    # Decorative timber panels. Vertical slats use Obramat 60x20 mm stock.
    slat_width: float = 60.0
    slat_thickness: float = 20.0
    slat_height: float = 430.0
    slat_gap: float = 12.5
    slat_count_per_face: int = 7
    slat_z: float = 125.0

    # Two concealed horizontal timber battens per panel; same 60x20 stock.
    batten_height: float = 60.0
    batten_thickness: float = 20.0
    batten_z_low: float = 185.0
    batten_z_high: float = 435.0

    # Symbolic floor-protection inserts/caps for the 40x40 legs.
    foot_cap_visible: float = 2.0

    @property
    def inner_opening(self) -> float:
        return self.length - 2 * self.frame_size

    @property
    def bottom_frame_z(self) -> float:
        return self.leg_clearance

    @property
    def top_frame_z(self) -> float:
        return self.body_height - self.frame_size

    @property
    def frame_rail_length(self) -> float:
        return self.inner_opening

    @property
    def support_top_z(self) -> float:
        return self.bag_support_z + self.support_size

    @property
    def bag_inner_opening(self) -> float:
        return self.bag_frame_outer - 2 * self.support_size

    @property
    def bag_height(self) -> float:
        return self.bag_frame_z - self.support_top_z

    @property
    def bag_frame_side_cut(self) -> float:
        return self.bag_inner_opening

    @property
    def slat_side_margin(self) -> float:
        occupied = (
            self.slat_count_per_face * self.slat_width
            + (self.slat_count_per_face - 1) * self.slat_gap
        )
        return (self.inner_opening - occupied) / 2

    @property
    def tray_side_clearance(self) -> float:
        return (self.inner_opening - self.tray_width) / 2

    @property
    def tray_to_bottom_frame_clearance(self) -> float:
        return self.bottom_frame_z - (self.tray_z + self.tray_wall_height)

    @property
    def bag_volume_litres(self) -> float:
        return (
            self.bag_inner_opening
            * self.bag_inner_opening
            * self.bag_height
            / 1_000_000
        )
