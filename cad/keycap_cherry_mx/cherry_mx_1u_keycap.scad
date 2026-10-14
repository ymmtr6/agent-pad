/*
  FDM-friendly 1U keycap for Cherry MX compatible switches.

  Units: millimetres
  Default orientation: switch/stem opening faces down.
  Set `part` to "fit_test" before printing a complete cap for the first time.
*/

part = "keycap"; // [keycap, keyset, fit_test, pattern_2d, keymap_2d]
surface_pattern = "agentpad"; // [agentpad, task, refactor, test, none]
task_number = 1; // [1:6]

// Keycap envelope (1U key pitch is normally 19.05 mm).
bottom_width = 18.1;
bottom_depth = 18.1;
top_width = 15.4;
top_depth = 15.4;
front_height = 9.0;
back_height = 9.0;
corner_radius = 1.00;

// FDM shell. 1.20 mm is three lines with a 0.4 mm nozzle.
wall = 1.60;
roof = 2.00;

// Cherry MX cross socket. Increase clearance if the first fit is too tight.
stem_cross_length = 4.10;
stem_cross_thickness = 1.25;
stem_clearance = 0.05; // snug fit; added to every side
stem_depth = 4.20;
stem_boss_diameter = 5.50;
// Start at the skirt plane so the central boss prints as its own supported
// pillar. At 5.5 mm OD it clears the switch recess while supporting the roof.
stem_boss_bottom = 0.00;

// Flat top for face-down FDM printing and a smooth finger-contact surface.
dish_depth = 0.00;
dish_radius = 45;

// AgentPad top mark: sized for a 0.4 mm nozzle and 0.12-0.16 mm layers.
pattern_depth = 0.45;
pattern_line_width = 0.60;
pattern_pad_diameter = 1.35;
pattern_pad_hole = 0.50;

$fn = 64;

height_mid = (front_height + back_height) / 2;
slope = atan((back_height - front_height) / bottom_depth);

module rounded_rectangle(size_x, size_y, radius) {
    offset(r = radius)
        square([size_x - 2 * radius, size_y - 2 * radius], center = true);
}

// A large tilted half-space whose top follows the desired front/back heights.
module below_top_plane(z_offset = 0) {
    translate([0, 0, height_mid + z_offset])
        rotate([slope, 0, 0])
            translate([0, 0, -50])
                cube([100, 100, 100], center = true);
}

module tapered_blank(width, depth, top_w, top_d, start_z = 0) {
    // Extrapolate the scale because the blank is taller than the clipping plane.
    // This makes `top_w`/`top_d` the dimensions near height_mid, not at z=14.
    scale_x = 1 + (top_w / width - 1) * (14 / height_mid);
    scale_y = 1 + (top_d / depth - 1) * (14 / height_mid);
    translate([0, 0, start_z])
        linear_extrude(height = 14, scale = [scale_x, scale_y])
            rounded_rectangle(width, depth, corner_radius);
}

module outer_body() {
    intersection() {
        tapered_blank(bottom_width, bottom_depth, top_width, top_depth);
        below_top_plane();
    }
}

module inner_void() {
    inner_bottom_w = bottom_width - 2 * wall;
    inner_bottom_d = bottom_depth - 2 * wall;
    inner_top_w = top_width - 2 * wall;
    inner_top_d = top_depth - 2 * wall;

    intersection() {
        tapered_blank(inner_bottom_w, inner_bottom_d,
                      inner_top_w, inner_top_d, -0.10);
        below_top_plane(-roof);
    }
}

module fingertip_dish() {
    // Cylinder axis follows the sloped top from front to back.
    rotate([slope, 0, 0])
        translate([0, 0, height_mid + dish_radius - dish_depth])
            rotate([90, 0, 0])
                cylinder(h = 40, r = dish_radius, center = true);
}

module cross_socket(extra_clearance = stem_clearance) {
    cross_l = stem_cross_length + 2 * extra_clearance;
    cross_t = stem_cross_thickness + 2 * extra_clearance;

    union() {
        translate([-cross_l / 2, -cross_t / 2, 0])
            cube([cross_l, cross_t, stem_depth + 0.20]);
        translate([-cross_t / 2, -cross_l / 2, 0])
            cube([cross_t, cross_l, stem_depth + 0.20]);
    }
}

module stem_boss() {
    boss_height = height_mid - roof - stem_boss_bottom + 0.25;
    translate([0, 0, stem_boss_bottom])
        cylinder(h = boss_height, d = stem_boss_diameter);
}

module trace_2d(point_a, point_b, width = pattern_line_width) {
    hull() {
        translate(point_a) circle(d = width, $fn = 20);
        translate(point_b) circle(d = width, $fn = 20);
    }
}

module circuit_pad_2d(point) {
    translate(point)
        difference() {
            circle(d = pattern_pad_diameter, $fn = 24);
            circle(d = pattern_pad_hole, $fn = 20);
        }
}

module agentpad_pattern_2d() {
    // A monogram drawn as PCB traces. The three hollow circles echo plated
    // pads, while the middle branch suggests an autonomous-agent flow graph.
    trace_2d([-3.5, -3.0], [0, 3.1]);
    trace_2d([0, 3.1], [3.5, -3.0]);
    trace_2d([-1.65, -0.15], [1.65, -0.15]);
    trace_2d([0, 3.1], [0, 4.0], 0.48);

    circuit_pad_2d([-3.5, -3.0]);
    circuit_pad_2d([3.5, -3.0]);
    circuit_pad_2d([0, 4.0]);

    // Small square node mirrors the square switch openings on AgentPad Rev.2.
    translate([-0.70, -0.85])
        difference() {
            square([1.40, 1.40]);
            translate([0.45, 0.45]) square([0.50, 0.50]);
        }
}

module task_pattern_2d(number = 1) {
    // Six numbered rings are the six agent/task status slots in the AgentPad
    // workflow. A small PCB pad at the top preserves the hardware visual theme.
    difference() {
        circle(d = 7.0, $fn = 6);
        circle(d = 5.75, $fn = 6);
    }
    translate([0, 0.05])
        text(str(number), size = 4.3,
             font = "Liberation Sans:style=Bold",
             halign = "center", valign = "center");
    trace_2d([0, 3.0], [0, 4.0], 0.48);
    circuit_pad_2d([0, 4.0]);
}

module arrow_head_2d(point) {
    trace_2d([point[0] - 0.9, point[1] - 0.75], point, 0.55);
    trace_2d([point[0] - 0.9, point[1] + 0.75], point, 0.55);
}

module refactor_pattern_2d() {
    // Git-style split paths: the AgentPad ACT06 / REFACTOR operation.
    trace_2d([-3.6, -2.6], [-1.5, -2.6]);
    trace_2d([-1.5, -2.6], [0.5, -0.5]);
    trace_2d([0.5, -0.5], [3.4, -0.5]);
    trace_2d([-1.5, -2.6], [0.5, 2.25]);
    trace_2d([0.5, 2.25], [3.4, 2.25]);
    circuit_pad_2d([-3.6, -2.6]);
    circuit_pad_2d([-1.5, -2.6]);
    arrow_head_2d([3.4, -0.5]);
    arrow_head_2d([3.4, 2.25]);
}

module test_pattern_2d() {
    // A checked test result: the AgentPad ACT07 / TEST operation.
    difference() {
        offset(r = 0.65) square([6.7, 6.7], center = true);
        offset(r = 0.18) square([5.55, 5.55], center = true);
    }
    trace_2d([-2.25, -0.15], [-0.55, -1.85], 0.72);
    trace_2d([-0.55, -1.85], [2.55, 2.05], 0.72);
}

module selected_pattern_2d(kind = surface_pattern, number = task_number) {
    if (kind == "agentpad") agentpad_pattern_2d();
    else if (kind == "task") task_pattern_2d(number);
    else if (kind == "refactor") refactor_pattern_2d();
    else if (kind == "test") test_pattern_2d();
}

module top_surface_engraving(kind = surface_pattern, number = task_number) {
    // Cut the artwork into the flat face. When printed face-down, this keeps
    // the whole finger-contact plane against the build plate and leaves the
    // legends as shallow recessed marks instead of rough raised features.
    rotate([slope, 0, 0])
        translate([0, 0, height_mid - pattern_depth])
            linear_extrude(height = pattern_depth + 0.20)
                selected_pattern_2d(kind, number);
}

module keycap(kind = surface_pattern, number = task_number) {
    difference() {
        union() {
            difference() {
                outer_body();
                inner_void();
                fingertip_dish();
            }
            stem_boss();
        }

        translate([0, 0, stem_boss_bottom - 0.10])
            cross_socket();
        if (kind != "none") top_surface_engraving(kind, number);
    }
}

module agentpad_keyset() {
    pitch = 21.0;
    // Physical order mirrors AgentPad Rev.2: SW1..SW3, SW4..SW6,
    // SW7..SW8, with the encoder occupying the open bottom-right position.
    translate([-pitch,  pitch, 0]) keycap("task", 1);
    translate([0,       pitch, 0]) keycap("task", 2);
    translate([pitch,   pitch, 0]) keycap("task", 3);
    translate([-pitch,      0, 0]) keycap("task", 4);
    translate([0,           0, 0]) keycap("task", 5);
    translate([pitch,       0, 0]) keycap("task", 6);
    translate([-pitch, -pitch, 0]) keycap("refactor");
    translate([0,      -pitch, 0]) keycap("test");
}

module agentpad_keymap_2d() {
    pitch = 11.5;
    translate([-pitch,  pitch]) task_pattern_2d(1);
    translate([0,       pitch]) task_pattern_2d(2);
    translate([pitch,   pitch]) task_pattern_2d(3);
    translate([-pitch,      0]) task_pattern_2d(4);
    translate([0,           0]) task_pattern_2d(5);
    translate([pitch,       0]) task_pattern_2d(6);
    translate([-pitch, -pitch]) refactor_pattern_2d();
    translate([0,      -pitch]) test_pattern_2d();
    translate([pitch,  -pitch]) {
        difference() {
            circle(d = 7.6);
            circle(d = 5.8);
        }
        translate([0, -5.0])
            text("ENC", size = 1.8, font = "Liberation Sans:style=Bold",
                 halign = "center", valign = "center");
    }
}

module one_fit_socket(clearance, label_text) {
    difference() {
        union() {
            // Match the real keycap boss envelope so the coupon also detects
            // interference with the switch's recessed top housing.
            cylinder(h = 5.0, d = stem_boss_diameter);
            translate([-4.25, -5.25, 0]) cube([8.5, 3.0, 1.0]);
        }
        // Open upward so the coupon prints flat without support. The 0.70 mm
        // floor is thick enough for 4-5 layers at the recommended settings.
        translate([0, 0, 0.70])
            cross_socket(clearance);
    }

    // Raised number is intentionally simple and may be omitted by some slicers.
    translate([0, -4.45, 1.0])
        linear_extrude(0.45)
            text(label_text, size = 1.8, halign = "center", valign = "center");
}

module fit_test() {
    translate([-11, 0, 0]) one_fit_socket(0.00, "00");
    one_fit_socket(0.05, "05");
    translate([11, 0, 0]) one_fit_socket(0.10, "10");
}

if (part == "keycap") {
    keycap();
} else if (part == "keyset") {
    agentpad_keyset();
} else if (part == "fit_test") {
    fit_test();
} else if (part == "keymap_2d") {
    agentpad_keymap_2d();
} else {
    selected_pattern_2d();
}
