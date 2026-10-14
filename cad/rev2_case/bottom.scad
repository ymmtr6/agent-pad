// Rev2 底ケース（トレイ）
// 基板は四隅の柱とソケット下の支えで受け、外周の壁で位置決めする。
// part = "bottom": ねじ止めなし / "bottom_insert": 四隅の柱に M2 熱圧入インサートの下穴 / "insert_test": 下穴径テスト
// 印刷向き: 床を下にしてそのまま、サポートなし。
// PCB 座標（左上原点・下向き+y）は pcb() で上から見た向きへ変換する。
part = "bottom"; // [bottom, bottom_insert, insert_test]

pcb_w = 62;
pcb_h = 80;
pcb_r = 2;
pcb_thickness = 1.6;
socket_height = 1.9; // 実測: 基板+ソケット 3.5 mm

clearance = 0.3; // 基板外周と壁の隙間
wall = 2.0;
floor_thickness = 2.0;
cavity = 5.0; // 床上面から基板裏面まで。ヘッダーピン等はこれ未満に切る
socket_gap = 0.1; // ソケット底面と支えの隙間

boss_top_diameter = 4.0; // 基板に触れる部分。銅箔禁止領域 Ø5 以内
boss_top_height = 1.0;
boss_diameter = 6.0;

// M2-3-3 インサート（長さ 3 mm）。下穴 Ø2.85 / 深さ 4.1 mm 以上が目安。
// 柱上端の Ø4 部は肉厚が薄いため、インサートは柱上面から insert_recess だけ沈めて Ø6 部に収める。
insert_hole = 2.9; // insert_test で決定（2026-10-12）
insert_recess = 1.0;
insert_hole_floor = 1.0; // 下穴の底に残す床厚。M2×12 の先端まで逃がす
insert_test_holes = [2.7, 2.8, 2.85, 2.9, 3.0];

usb_notch_width = 14; // USB ケーブル差し込み側の壁の切り欠き
usb_notch_depth = 1.5;
$fn = 48;

key_centres = [
    [11.95, 34.0], [31.0, 34.0], [50.05, 34.0],
    [11.95, 53.05], [31.0, 53.05], [50.05, 53.05],
    [11.95, 72.1], [31.0, 72.1]
];
mount_holes = [[2.5, 2.5], [59.5, 2.5], [2.5, 77.5], [59.5, 77.5]];

pcb_bottom_z = floor_thickness + cavity;
wall_top_z = pcb_bottom_z + pcb_thickness;
outer_r = pcb_r + clearance + wall;

module pcb(p) {
    translate([p[0], pcb_h - p[1]]) children();
}

module rounded_rect(w, h, r) {
    hull() for (x = [r, w - r]) for (y = [r, h - r])
        translate([x, y]) circle(r=r);
}

// ソケット本体（スイッチ中心から x -6.35..5.08 / y -6.985..-0.635）の内側 0.5 mm。
// スイッチ中央ボスと位置決めピンが基板裏へ突き出す範囲は避ける。
module socket_support() {
    linear_extrude(height=cavity - socket_height - socket_gap) difference() {
        translate([-5.85, 1.135]) square([10.43, 5.35]);
        circle(r=2.5);
        for (x = [-5.08, 5.08]) translate([x, 0]) circle(r=1.3);
    }
}

module tray(inserts) {
    difference() {
        union() {
            difference() {
                translate([-clearance - wall, -clearance - wall])
                    linear_extrude(height=wall_top_z)
                        rounded_rect(pcb_w + 2*(clearance + wall), pcb_h + 2*(clearance + wall), outer_r);
                translate([-clearance, -clearance, floor_thickness])
                    linear_extrude(height=wall_top_z)
                        rounded_rect(pcb_w + 2*clearance, pcb_h + 2*clearance, pcb_r + clearance);
            }
            for (p = mount_holes) pcb(p) {
                cylinder(d=boss_diameter, h=pcb_bottom_z - boss_top_height);
                cylinder(d=boss_top_diameter, h=pcb_bottom_z);
            }
            for (p = key_centres) pcb(p) translate([0, 0, floor_thickness]) socket_support();
        }
        translate([pcb_w/2 - usb_notch_width/2, pcb_h, wall_top_z - usb_notch_depth])
            cube([usb_notch_width, clearance + wall + 1, usb_notch_depth + 1]);
        if (inserts) for (p = mount_holes) pcb(p)
            translate([0, 0, insert_hole_floor]) cylinder(d=insert_hole, h=pcb_bottom_z);
    }
}

// 実物と同じ形の柱を 5 本並べた下穴テスト。台の手前の切り欠き数が 1〜5 本で insert_test_holes の順。
module insert_test() {
    pitch = 10;
    difference() {
        union() {
            cube([pitch*len(insert_test_holes), pitch, floor_thickness]);
            for (i = [0:len(insert_test_holes) - 1]) translate([pitch*(i + 0.5), pitch/2, 0]) {
                cylinder(d=boss_diameter, h=pcb_bottom_z - boss_top_height);
                cylinder(d=boss_top_diameter, h=pcb_bottom_z);
            }
        }
        for (i = [0:len(insert_test_holes) - 1]) {
            translate([pitch*(i + 0.5), pitch/2, insert_hole_floor])
                cylinder(d=insert_test_holes[i], h=pcb_bottom_z);
            for (n = [0:i])
                translate([pitch*i + 1.0 + n*1.2, -0.01, floor_thickness - 0.8]) cube([0.6, 1.0, 1]);
        }
    }
}

if (part == "insert_test") insert_test();
else tray(part == "bottom_insert");
