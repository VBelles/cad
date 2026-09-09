from dataclasses import dataclass


@dataclass(frozen=True)
class PlanterConfig:
    """Fabrication dimensions in millimetres unless stated otherwise."""

    # Finished envelope.
    length: float = 600.0
    depth: float = 600.0
    body_height: float = 600.0

    # Main welded frame: 40x40x1.5 steel.
    frame_size: float = 40.0
    frame_wall: float = 1.5
    leg_clearance: float = 80.0
    top_cap_flap_length: float = 40.0

    # Legacy v5 bag/support fields (kept so existing revisions still build).
    support_size: float = 20.0
    support_wall: float = 1.5
    bag_support_z: float = 120.0
    bag_support_crossbar_count: int = 5
    bag_frame_outer: float = 500.0
    bag_frame_z: float = 563.0
    bag_wall: float = 2.0
    bag_fold_thickness: float = 1.0

    # Continuous clamping frame: 30x3 flat bar.
    bag_clamp_width: float = 30.0
    bag_clamp_thickness: float = 3.0
    bag_clamp_overhang: float = 5.0
    bag_clamp_fasteners_per_side: int = 3
    clamp_washer_radius: float = 5.0
    clamp_washer_thickness: float = 1.0
    clamp_head_radius: float = 4.0
    clamp_head_height: float = 3.0

    # 20x20x3 angle steel.
    angle_leg: float = 20.0
    angle_wall: float = 3.0
    bag_ledge_length: float = 100.0

    # Legacy fabricated tray dimensions; v6 uses module tray target fields below.
    tray_width: float = 510.0
    tray_depth: float = 500.0
    tray_z: float = 48.0
    tray_wall_height: float = 10.0
    tray_sheet: float = 1.0
    drain_nominal_diameter: float = 20.0
    drain_local_x: float = 400.0
    drain_local_y: float = 450.0

    # Decorative timber. Default slats are now 10 mm finished, intended to be
    # ripped from raw fir boards. Legacy count/height fields remain for v5.
    slat_width: float = 60.0
    slat_thickness: float = 10.0
    slat_height: float = 430.0
    slat_gap: float = 12.5
    slat_count_per_face: int = 7
    slat_z: float = 125.0

    batten_height: float = 60.0
    batten_thickness: float = 20.0
    batten_z_low: float = 185.0
    batten_z_high: float = 435.0
    panel_outer_inset: float = 0.0

    # Current v5 end-bracket geometry.
    panel_bracket_width: float = 20.0
    panel_bracket_leg: float = 20.0
    panel_bracket_wall: float = 3.0
    panel_brackets_per_batten: int = 2
    panel_battens_per_face: int = 2

    # Compatibility with older centred-bracket wrapper.
    panel_bracket_length: float = 60.0
    panel_brackets_per_face: int = 2
    panel_bracket_fasteners_each: int = 2
    panel_bracket_screw_spacing: float = 30.0

    panel_mount_screw_diameter: float = 5.0
    panel_mount_screw_length: float = 16.0
    panel_mount_head_radius: float = 4.5
    panel_mount_head_thickness: float = 3.0

    # Legacy v4 mounting tabs (not exported by v5/v6).
    panel_tab_length: float = 50.0
    panel_tab_height: float = 30.0
    panel_tab_thickness: float = 3.0
    panel_tab_post_overlap: float = 20.0

    foot_cap_visible: float = 2.0

    # ---- v6 modular parameters --------------------------------------------
    bays_x: int = 1
    soil_depth: float = 443.0
    bag_top_clearance: float = 17.0
    bag_frame_margin: float = 10.0
    support_max_clear_gap: float = 90.0
    tray_target_width: float = 500.0
    tray_target_depth: float = 500.0
    tray_edge_margin: float = 10.0
    tray_target_z: float = 35.0
    tray_target_height: float = 30.0
    tray_target_wall: float = 3.0
    panel_vertical_clearance: float = 5.0
    batten_edge_center_offset: float = 90.0
    panel_max_batten_spacing: float = 300.0

    # ---- Legacy derived geometry ------------------------------------------
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
        return self.panel_outer_inset + self.panel_total_depth

    @property
    def panel_batten_front_offset(self) -> float:
        return self.panel_outer_inset + self.slat_thickness

    @property
    def panel_bracket_count_per_face(self) -> int:
        return self.panel_brackets_per_batten * self.panel_battens_per_face

    @property
    def tray_side_clearance(self) -> float:
        return (self.inner_opening - self.tray_width) / 2

    @property
    def tray_to_bottom_frame_clearance(self) -> float:
        return self.bottom_frame_z - (self.tray_z + self.tray_wall_height)

    @property
    def bag_volume_litres(self) -> float:
        return self.bag_inner_opening * self.bag_inner_opening * self.bag_height / 1_000_000

    # ---- v6 modular derived geometry --------------------------------------
    @property
    def station_count(self) -> int:
        return self.bays_x + 1

    @property
    def bay_opening_length(self) -> float:
        return (self.length - self.station_count * self.frame_size) / self.bays_x

    @property
    def bay_pitch(self) -> float:
        return self.bay_opening_length + self.frame_size

    @property
    def module_inner_depth(self) -> float:
        return self.depth - 2 * self.frame_size

    @property
    def module_bag_frame_outer_x(self) -> float:
        return self.bay_opening_length - 2 * self.bag_frame_margin

    @property
    def module_bag_frame_outer_y(self) -> float:
        return self.module_inner_depth - 2 * self.bag_frame_margin

    @property
    def module_bag_inner_x(self) -> float:
        return self.module_bag_frame_outer_x - 2 * self.support_size

    @property
    def module_bag_inner_y(self) -> float:
        return self.module_bag_frame_outer_y - 2 * self.support_size

    @property
    def module_bag_frame_top_z(self) -> float:
        return self.body_height - self.bag_top_clearance

    @property
    def module_bag_frame_z(self) -> float:
        return self.module_bag_frame_top_z - self.support_size

    @property
    def module_bag_support_top_z(self) -> float:
        return self.module_bag_frame_top_z - self.soil_depth

    @property
    def module_bag_support_z(self) -> float:
        return self.module_bag_support_top_z - self.support_size

    @property
    def module_bag_clamp_outer_x(self) -> float:
        return self.module_bag_frame_outer_x + 2 * self.bag_clamp_overhang

    @property
    def module_bag_clamp_outer_y(self) -> float:
        return self.module_bag_frame_outer_y + 2 * self.bag_clamp_overhang

    @property
    def module_bag_clamp_z(self) -> float:
        return self.module_bag_frame_top_z + self.bag_fold_thickness

    @property
    def module_support_crossbar_count(self) -> int:
        count = 2
        while (
            self.module_bag_inner_x - count * self.support_size
        ) / (count - 1) > self.support_max_clear_gap:
            count += 1
        return count

    @property
    def module_support_clear_gap(self) -> float:
        count = self.module_support_crossbar_count
        return (self.module_bag_inner_x - count * self.support_size) / (count - 1)

    @property
    def module_tray_width(self) -> float:
        return min(self.tray_target_width, self.bay_opening_length - 2 * self.tray_edge_margin)

    @property
    def module_tray_depth(self) -> float:
        return min(self.tray_target_depth, self.module_inner_depth - 2 * self.tray_edge_margin)

    @property
    def module_tray_vertical_clearance(self) -> float:
        return self.bottom_frame_z - (self.tray_target_z + self.tray_target_height)

    @property
    def module_panel_bottom_z(self) -> float:
        return self.bottom_frame_z + self.frame_size + self.panel_vertical_clearance

    @property
    def module_panel_top_z(self) -> float:
        return self.top_frame_z - self.panel_vertical_clearance

    @property
    def module_panel_height(self) -> float:
        return self.module_panel_top_z - self.module_panel_bottom_z

    @property
    def module_panel_batten_count(self) -> int:
        import math
        return max(2, math.ceil(self.module_panel_height / self.panel_max_batten_spacing))

    @property
    def module_bag_volume_litres_each(self) -> float:
        return self.module_bag_inner_x * self.module_bag_inner_y * self.soil_depth / 1_000_000

    @property
    def module_bag_volume_litres_total(self) -> float:
        return self.module_bag_volume_litres_each * self.bays_x
