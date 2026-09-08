from dataclasses import dataclass


@dataclass(frozen=True)
class PlanterConfig:
    """Fabrication dimensions in millimetres unless stated otherwise."""

    # Finished envelope, including the four continuous 40x40 steel uprights/legs.
    length: float = 600.0
    depth: float = 600.0
    body_height: float = 600.0

    # Main welded frame: Obramat steel tube 40x40x1.5 mm.
    frame_size: float = 40.0
    frame_wall: float = 1.5
    leg_clearance: float = 80.0
    top_cap_flap_length: float = 40.0

    # Internal load platform: Obramat steel tube 20x20x1.5 mm.
    # Five parallel rails directly support the geotextile bottom; drainage remains open.
    support_size: float = 20.0
    support_wall: float = 1.5
    bag_support_z: float = 120.0
    bag_support_crossbar_count: int = 5

    # Removable bag rim frame, supported just inside the 40 mm top border.
    bag_frame_outer: float = 500.0
    bag_frame_z: float = 563.0
    bag_wall: float = 2.0
    bag_fold_thickness: float = 1.0  # visual CAD representation of doubled geotextile

    # Continuous clamping frame: Obramat S275JR flat bar 30x3 mm.
    # It clamps the folded geotextile against the 20x20 tube continuously.
    bag_clamp_width: float = 30.0
    bag_clamp_thickness: float = 3.0
    bag_clamp_overhang: float = 5.0
    bag_clamp_fasteners_per_side: int = 3
    clamp_washer_radius: float = 5.0
    clamp_washer_thickness: float = 1.0
    clamp_head_radius: float = 4.0
    clamp_head_height: float = 3.0

    # Obramat steel angle 20x20x3 mm.
    angle_leg: float = 20.0
    angle_wall: float = 3.0
    bag_ledge_length: float = 100.0

    # Removable drain tray under the lower frame, between the legs.
    # Kept unchanged for now; material/fabrication method remains an open decision.
    tray_width: float = 510.0
    tray_depth: float = 500.0
    tray_z: float = 48.0
    tray_wall_height: float = 10.0
    tray_sheet: float = 1.0
    drain_nominal_diameter: float = 20.0
    drain_local_x: float = 400.0
    drain_local_y: float = 450.0

    # Decorative timber panels. Current visual uses 60x20 mm stock, but panel
    # depth is deliberately parameterised so slats can later become 10/15 mm.
    slat_width: float = 60.0
    slat_thickness: float = 20.0
    slat_height: float = 430.0
    slat_gap: float = 12.5
    slat_count_per_face: int = 7
    slat_z: float = 125.0

    # Two concealed horizontal timber battens per panel; same 60x20 stock for now.
    # They overlap the lower/top steel rails vertically so the two small mounting
    # brackets can bolt directly into the battens without corner hardware.
    batten_height: float = 60.0
    batten_thickness: float = 20.0
    batten_z_low: float = 110.0
    batten_z_high: float = 510.0

    # Panel depth/alignment. 0 = timber outer face flush with the outer steel face.
    # For an inner-flush panel set this to frame_size - panel_total_depth.
    panel_outer_inset: float = 0.0

    # Two small 20x20x3 angle brackets per timber face: one on the lower rail and
    # one on the upper rail, both centred on that face. Each bracket uses two M5
    # fasteners into the timber batten. Moving the bracket in depth accommodates
    # a different slat thickness without changing the steel corner geometry.
    panel_bracket_length: float = 60.0
    panel_bracket_leg: float = 20.0
    panel_bracket_wall: float = 3.0
    panel_brackets_per_face: int = 2
    panel_bracket_fasteners_each: int = 2
    panel_bracket_screw_spacing: float = 30.0
    panel_mount_screw_diameter: float = 5.0
    panel_mount_screw_length: float = 16.0
    panel_mount_head_radius: float = 4.5
    panel_mount_head_thickness: float = 3.0

    # Legacy tab dimensions are retained only because the v4 base builder still
    # creates them before the v5 wrapper removes/replaces them. They are not part
    # of the exported v5 design and can disappear when planter.py is consolidated.
    panel_tab_length: float = 50.0
    panel_tab_height: float = 30.0
    panel_tab_thickness: float = 3.0
    panel_tab_post_overlap: float = 20.0

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
    def bag_bottom_z(self) -> float:
        return self.support_top_z

    @property
    def bag_frame_top_z(self) -> float:
        return self.bag_frame_z + self.support_size

    @property
    def bag_height(self) -> float:
        return self.bag_frame_top_z - self.bag_bottom_z

    @property
    def bag_frame_side_cut(self) -> float:
        return self.bag_inner_opening

    @property
    def bag_xy(self) -> float:
        return (self.length - self.bag_inner_opening) / 2

    @property
    def bag_support_clear_gap(self) -> float:
        return (
            self.bag_inner_opening - self.bag_support_crossbar_count * self.support_size
        ) / (self.bag_support_crossbar_count - 1)

    @property
    def bag_support_pitch(self) -> float:
        return self.support_size + self.bag_support_clear_gap

    @property
    def bag_clamp_outer(self) -> float:
        return self.bag_frame_outer + 2 * self.bag_clamp_overhang

    @property
    def bag_clamp_side_cut(self) -> float:
        return self.bag_clamp_outer - 2 * self.bag_clamp_width

    @property
    def bag_clamp_z(self) -> float:
        return self.bag_frame_top_z + self.bag_fold_thickness

    @property
    def slat_side_margin(self) -> float:
        occupied = (
            self.slat_count_per_face * self.slat_width
            + (self.slat_count_per_face - 1) * self.slat_gap
        )
        return (self.inner_opening - occupied) / 2

    @property
    def panel_total_depth(self) -> float:
        return self.slat_thickness + self.batten_thickness

    @property
    def panel_back_offset(self) -> float:
        """Distance from the exterior steel face to the inner face of a panel."""
        return self.panel_outer_inset + self.panel_total_depth

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
