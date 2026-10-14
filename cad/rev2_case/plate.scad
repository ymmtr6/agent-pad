// Rev2 キー保持プレート（ねじ止めなし）
// スイッチをソケットへ挿して保持する。四隅の柱は傾き止めで、基板とは standoff_gap だけ離す。
// 印刷向き: z=0 が指側の上面。上面をビルドプレートに置き、柱が上に伸びる向きでサポートなし印刷。
// 座標は PCB 座標（左上原点・下向き+y）をそのまま使う。印刷姿勢からX軸回りに裏返すと実装向きになる。
part = "plate"; // [plate, fit_test]

plate_thickness = 1.5;
switch_opening = 14.0; // fit_test の結果で調整する
plate_top_above_pcb = 5.0; // PCB表面からプレート上面まで
standoff_gap = 0.2; // スイッチのクリップ位置と競合させない
standoff_diameter = 4.0; // 基板の銅箔禁止領域 Ø5 以内
$fn = 48;

mount_holes = [[2.5, 2.5], [59.5, 2.5], [2.5, 77.5], [59.5, 77.5]];

module profile() {
    hull() {
        for (x = [2, 60]) for (y = [2, 78])
            translate([x, y]) circle(r=2);
    }
}

module plate() {
    linear_extrude(height=plate_thickness) difference() {
        profile();
        translate([21, -1]) square([20, 26]); // MCU/USB access.
        for (row = [0:2]) for (col = [0:2]) {
            // Lower-right opening clears the EC11 body.
            translate([11.95 + col*19.05, 34 + row*19.05])
                square([switch_opening, switch_opening], center=true);
        }
    }
    for (p = mount_holes)
        translate(p) cylinder(d=standoff_diameter, h=plate_top_above_pcb - standoff_gap);
}

// 開口 13.9 / 14.0 / 14.1 mm の嵌合テスト。開口の左側の切り欠き数が 1 / 2 / 3。
module fit_test() {
    sizes = [13.9, 14.0, 14.1];
    linear_extrude(height=plate_thickness) difference() {
        square([3*19.05, 19.05]);
        for (i = [0:2]) {
            translate([19.05*(i + 0.5), 19.05/2])
                square([sizes[i], sizes[i]], center=true);
            for (n = [0:i])
                translate([19.05*i + 0.4 + n*0.9, -0.01]) square([0.5, 1.2]);
        }
    }
}

if (part == "fit_test") fit_test();
else plate();
