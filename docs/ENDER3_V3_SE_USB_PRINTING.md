# Ender-3 V3 SE USB接続・印刷運用レポート

作成日: 2026-09-02  
対象: Creality Ender-3 V3 SE / AgentPadキーキャップ  
状態: 実機で3ジョブのUSB印刷完了

## 1. 確認済みの構成

| 項目 | 確認値 |
| --- | --- |
| プリンター | Creality Ender-3 V3 SE |
| ファームウェア | Marlin V1.1.0, build 2025-04-22 |
| USBホスト | `rmm4.local`（macOS 26.5.1） |
| シリアルデバイス | `/dev/cu.usbserial-1140` |
| ボーレート | 115200 baud |
| レベリング | CR Touch / G-codeの `G29` |
| スライサー | PrusaSlicer 2.9.6 |
| 実績プロファイル | `cad/keycap_cherry_mx/ender3_v3_se_pla.ini` |
| 送信プログラム | `scripts/serial_print.py` |

接続経路は次のとおり。

```text
作業PC ── SSH/SCP ──> rmm4.local ── USBシリアル ──> Ender-3 V3 SE
        G-code転送       115200 baud       Marlin
```

`rmm4.local` がG-codeを1コマンドずつ送信し、プリンターの `ok` を確認して
から次へ進む。作業PCを直接USB接続する必要はないが、SSH接続と
`rmm4.local` の稼働を印刷終了まで維持する必要がある。

## 2. 初回接続とデバイス確認

プリンターの電源を入れ、USBケーブルを `rmm4.local` に接続する。

```sh
ssh rmm4.local
ls -l /dev/cu.usbserial-*
```

今回のデバイス名は `/dev/cu.usbserial-1140` だった。ただし、USBポートや
再接続の順番で末尾が変わる可能性があるため、毎回列挙して確認する。

同じポートを別のソフトが使用していないことも確認する。

```sh
lsof /dev/cu.usbserial-1140
```

何も表示されなければ未使用。Pronterface、OctoPrint、別の送信スクリプト、
シリアルモニターを同時に開かないこと。SDカード印刷中にもUSB送信を開始しない。

送信プログラムをホストへ配置する。

```sh
scp scripts/serial_print.py rmm4.local:/tmp/serial_print.py
```

G-codeを指定せず実行すると、接続、機種情報、温度だけを確認して終了する。

```sh
ssh -tt rmm4.local \
  'python3 /tmp/serial_print.py /dev/cu.usbserial-1140'
```

正常時は `CONNECTED` に続いて `MACHINE_TYPE:Ender-3 V3 SE` と温度が表示
される。シリアルポートを開くとUSBシリアル変換チップ経由でコントローラーが
再起動する場合がある。このスクリプトは接続後3秒待ってから `M115` を送信する。

## 3. STLからG-codeを作る

キーキャップ8個セットの確認済みコマンドは次のとおり。

```sh
/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer \
  --load cad/keycap_cherry_mx/ender3_v3_se_pla.ini \
  --rotate-x 180 \
  --center 110,110 \
  --export-gcode \
  --output /tmp/agentpad_keyset8_facedown_usb.gcode \
  cad/keycap_cherry_mx/agentpad_keyset_8.stl
```

`--rotate-x 180` により、指が触れる平坦な面をビルドプレート側にする。文字は
0.45 mmの凹彫りで、内部サポートは使用しない。STLをスライサー上で拡大縮小
するとCherry MX軸の嵌合寸法も変わるため、倍率は100%のまま使用する。

確認済みPLA設定の要点:

- ノズル: 0.4 mm
- レイヤー: 初層0.20 mm、以降0.16 mm
- ノズル温度: 初層205°C、以降200°C
- ベッド温度: 60°C
- ブリム: 2 mm
- サポート: なし
- 開始処理: `G28`、`G29`、パージライン
- 終了処理: `M400`、`M104 S0`、`M140 S0`、ヘッド退避、`M84`

## 4. 送信前の検査

USB送信を始める前に、最低限次を確認する。

1. ビルドプレート上に前回の造形物や工具がない。
2. プレートが固定され、ノズル周辺に付着物がない。
3. フィラメント残量が十分で、絡みがない。
4. スライサーの機種、ノズル径、材料、倍率が正しい。
5. 全造形物が220 x 220 x 250 mmの範囲内にある。
6. 開始G-codeに原点復帰と必要なレベリングがある。
7. 終了G-codeにヒーター停止とモーター解除がある。
8. SDカード印刷や別のUSB制御ソフトが動作していない。

8キー印刷で確認したG-codeは約3.9 MB、141,508コマンド、PLA約10.48 cm3。
座標は機械範囲内で、ヒーター停止を含む終了処理も確認してから送信した。

## 5. G-code転送とUSB印刷

作業PCからG-codeを転送する。

```sh
scp /tmp/agentpad_keyset8_facedown_usb.gcode \
  rmm4.local:/tmp/agentpad_keyset8_facedown_usb.gcode
```

ファイルサイズを確認してから、フォアグラウンドで印刷を開始する。

```sh
ssh -tt rmm4.local \
  'ls -lh /tmp/agentpad_keyset8_facedown_usb.gcode && \
   python3 /tmp/serial_print.py \
     /dev/cu.usbserial-1140 \
     /tmp/agentpad_keyset8_facedown_usb.gcode'
```

正常なログの流れ:

```text
CONNECTED ... MACHINE_TYPE:Ender-3 V3 SE ...
PRINT_START commands=141508 file=agentpad_keyset8_facedown_usb.gcode
PROGRESS 500/141508 elapsed=... command='...' reply=ok
...
PRINT_DONE elapsed=8616s status=ok T:... /0.00 B:... /0.00
```

`PROGRESS` は500コマンドごと、および `G28`、`G29`、温度・終了処理などの
重要コマンドで表示される。`PRINT_DONE` と終了コード0を確認するまでSSHを
閉じない。作業PCと `rmm4.local` のスリープも無効にする。

この方式には印刷途中からの再開機能がない。ネットワーク切断、SSH終了、
ホスト停止が起きると安全停止しても造形物は継続できない。長時間運用では、
信頼できる有線ネットワークやホスト側の常駐ジョブ管理を別途検討する。

## 6. 監視と安全停止

開始後は特に次を確認する。

- `G28` とCR Touchの `G29` が `ok` で完了する。
- ベッドが60°C、ノズルが205°Cへ上がる。
- パージラインと8個すべての初層が定着する。
- フィラメントがノズルに巻き付いていない。
- ログに `Error:`、`Resend:`、timeout、`PRINT_ABORTED` がない。
- 完了時にノズル・ベッドの目標温度が0°Cになる。

通常中断は送信中の端末で `Ctrl-C` を1回押す。スクリプトは可能な範囲で
次を送信して終了する。

```text
M104 S0   ; ノズル停止
M140 S0   ; ベッド停止
M107      ; ファン停止
M84       ; モーター解除
```

煙、異臭、衝突、サーマルランナウェイなど切迫した危険がある場合は、ソフトの
応答を待たずプリンター本体の電源を切る。停止後、原因を解消してから再印刷する。

## 7. 実機印刷の記録

| ジョブ | コマンド数 | 実時間 | 結果 |
| --- | ---: | ---: | --- |
| MX軸フィットテスト | 25,393 | 1,093秒（18分13秒） | 成功 |
| Task 1 改訂キーキャップ | 19,086 | 1,382秒（23分02秒） | 成功、スイッチ装着確認 |
| 面下向き8キーセット | 141,508 | 8,616秒（2時間23分36秒） | 成功、エラー0 |

8キーのスライサー見積もりは約2時間4分だったが、実時間は約19分長かった。
USBでは1コマンドごとに `ok` を待つため、スライサー見積もりより余裕を持つ。

## 8. よくある問題

### シリアルデバイスが見つからない

- プリンター電源、USBケーブル、接続ポートを確認する。
- `ls /dev/cu.usbserial-*` を再実行する。
- 充電専用ではなくデータ通信対応のUSBケーブルを使う。

### `Resource busy` またはポートを開けない

- `lsof /dev/cu.usbserial-XXXX` で使用プロセスを確認する。
- 他のプリンター制御ソフトや送信スクリプトを終了する。
- 1つのシリアルポートを複数プログラムで共有しない。

### 接続直後に応答しない

- ポートを開いた際にMarlinが再起動する場合があるため、3秒以上待つ。
- デバイス名と115200 baudを確認する。
- USBを再接続した場合はデバイス名を再検出する。

### CR Touchで停止する

- プローブ、配線、ビルドプレート固定、ノズルの汚れを確認する。
- 手動で無理に続行せず、`G29` が正常終了してから印刷する。

### 初層が剥がれる

- プレートを洗浄し、油分を除去する。
- CR TouchとZオフセットを再確認する。
- 初層温度、ブリム、フィラメント状態を確認する。
- キーキャップの倍率は変えず、必要ならスライサー設定側を調整する。

### SSHが切断された

- 本スクリプトは `SIGHUP` を受けると安全停止を試みる。
- ヒーターの目標温度が0°Cかをプリンター画面で確認する。
- 途中からの再開はせず、造形物を除去して最初からやり直す。

## 9. 次回用チェックリスト

```text
[ ] プリンター電源・USB・フィラメントを確認
[ ] ベッドを清掃し、造形物がないことを確認
[ ] /dev/cu.usbserial-* を再検出
[ ] lsofでポート未使用を確認
[ ] STL倍率100%、向き、材料、温度を確認
[ ] G-codeの機械範囲、G28/G29、終了時ヒーターOFFを確認
[ ] G-codeをrmm4.localへ転送
[ ] M115でEnder-3 V3 SEを確認
[ ] SSHと両ホストの稼働を維持して印刷開始
[ ] 初層を目視確認
[ ] PRINT_DONE、目標温度0°C、M84を確認
[ ] プレートが冷えてから造形物を取り外す
```
