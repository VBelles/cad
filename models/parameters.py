from dataclasses import dataclass


@dataclass(frozen=True)
class PlanterConfig:
    """Fabrication dimensions in millimetres unless stated otherwise."""

    # Finished steel frame envelope. Timber slats sit flush inside this envelope.
    length: float = 600.0
    depth: float = 600.0
    body_height: float = 600.0

    # Main welded frame: Obramat 40x40x1.5 mm raw steel tube.
    frame_size: float = 40.0
    frame_wall: float = 1.5

    # Internal load-bearing frame: Obramat 20x20x1.5 mm steel tube.
    support_size: float = 20.0
    support_wall: float = 1.5
    bag_support_z: float = 125.0

    # Removable upper frame sewn into / captured by the geotextile bag edge.
    bag_frame_outer: float = 500.0
    bag_frame_z: float = 550.0
    bag_wall: float = 2.0

    # L-angle supports: Obramat 20x20x3 mm steel angle.
    angle_leg: float = 20.0
    angle_wall: float = 3.0
    upper_support_length: float = 100.0

    # Drain tray. 1 mm galvanised sheet, removable towards the rear service face.
    tray_width: float = 480.0
    tray_depth: float = 490.0
    tray_z: float = 110.0
    tray_wall_height: float = 10.0
    tray_sheet: float = 1.0
    tray_guide_length: float = 490.0
    drain_nominal_diameter: float = 20.0
    drain_local_x: float = 400.0
    drain_local_y: float = 450.0

    # Decorative timber cladding. Obramat 2500x60x20 mm abeto slat stock.
    slat_width: float = 60.0
    slat_thickness: float = 20.0
    slat_height: float = 495.0
    slat_gap: float = 12.5
    slat_count_per_face: int = 7

    # 20x4 mm steel flat-bar backing straps behind the timber slats.
    flat_width: float = 20.0
    flat_thickness: float = 4.0
    cladding_strap_z_low: float = 190.0
    cladding_strap_z_high: float = 410.0
    service_mount_tab_length: float = 50.0

    @property
    def inner_opening(self) -> float:
        return self.length - 2 * self.frame_size

    @property
    def upright_length(self) -> float:
        return self.body_height

    @property
    def frame_rail_length(self) -> float:
        return self.inner_opening

    @property
    def support_top_z(self) -> float:
        return self.bag_support_z + self.support_size

    @property
    def bag_bottom_z(self) -> float:
        return self.support_top_z

    @property
    def bag_height(self) -> float:
        return self.bag_frame_z - self.bag_bottom_z

    @property
    def bag_inner_opening(self) -> float:
        return self.bag_frame_outer - 2 * self.support_size

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
    def slat_z(self) -> float:
        return self.frame_size + (self.inner_opening - self.slat_height) / 2

    @property
    def tray_blank_width(self) -> float:
        return self.tray_width + 2 * self.tray_wall_height

    @property
    def tray_blank_depth(self) -> float:
        return self.tray_depth + 2 * self.tray_wall_height
