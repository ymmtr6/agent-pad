---
name: jlcdfm-check
description: JLCPCB 発注前に Gerber ZIP を JLCDFM (jlcdfm.com) にアップロードして DFM check を実行し、エラー項目を生成スクリプト側で潰して再確認する手順。「DFM check」「JLCDFM」「JLCONE の DFM」「JLCPCB に発注する前の確認」「発注オプション」などで使う。
---

# JLCDFM による DFM check と修正ループ

AgentPad の Gerber を JLCPCB に出す前に、JLCDFM で DFM エラーを 0 件にするための手順。
Claude in Chrome（`mcp__claude-in-chrome__*`）でブラウザを操作する。computer use は不要。

## 前提知識

- JLCONE（デスクトップアプリ）の DFM 結果は、jlcpcb.com のプロジェクトページ（Tasks / Files / Orders）には出ない。JLCONE の画面は Chrome から見えないので、**jlcdfm.com に ZIP を直接アップロードして同じチェックを再現する**。
- ユーザーが JLCDFM の viewer（`https://jlcdfm.com/viewer?pcbUploadFileId=...`）を開いている場合は、`tabs_context_mcp` でそのタブを見つけて結果を読むだけでよい。
- **アップロードするのは発注用の `manufacturing/agentpad_<rev>_gerber.zip`**。`*_complete.zip` には KiCad データ・スクリプト・STL などが入っていて Gerber もサブフォルダ下にあるので、発注にも DFM 確認にも使わない。ユーザーが complete を DFM にかけていたら指摘する。
- 面付けリビジョン（rev3 など）は `agentpad_<rev>_JLCPCB_panel.zip` が発注単位。どれを使うか曖昧なら AskUserQuestion で確認する。
- 結果の数字は各項目 **(Danger, Warning, Good)** の件数。Danger が 0 なら発注可能。

## 手順 1: アップロードして DFM check を実行

1. ToolSearch で必要なツールをまとめて読み込む:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__find,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__file_upload,mcp__claude-in-chrome__browser_batch`
2. 比較のために既存の結果タブを残したい場合は `tabs_create_mcp` で新しいタブを作る。
3. `browser_batch` で `navigate https://jlcdfm.com/` を実行し、`find "file input for uploading Gerber zip in main upload section"` でファイル入力の ref を取る（トップページのメインのアップロード欄。下部の "Try for Free" 欄は使わない）。
4. `file_upload` に ZIP の絶対パスを渡す。
5. `wait 10` → `screenshot (scale 0.5)` で viewer（URL が `/viewer?pcbUploadFileId=...` に変わる）へ遷移したか確認する。読み込みには 15〜30 秒かかる。
   - **アップロードが 96% などで止まったら**、jlcdfm.com を開き直して 1 回だけアップロードをやり直す。
6. viewer では解析がまだ実行されていない。`find "DFM check button in left PCB DFM panel"` → `left_click` → `wait 10` → `get_page_text` で全項目の件数を取る。
7. viewer の URL をユーザーに伝える（ユーザーが同じ画面を見られるように）。

## 手順 2: エラー項目の詳細を確認

- Danger が 1 以上の項目は、`find "Details button in the '<項目名>' row"` → クリック → `screenshot` で座標と層を確認する。ダイアログは右上の × で閉じる。
- 座標を KiCad データ（`kicad/*.kicad_pcb`）と突き合わせて、原因のパッド・トレース・ラベルを特定する。Gerber の Y は KiCad の Y と符号が逆になる。
- 原因を説明するときは、**実害があるか（発注を止めるべきか）**と、**生成スクリプトのどこで直すか**を分けて書く。

### 過去に出た項目と対処（AgentPad rev2 single / rev3 panel）

| 項目 | 原因 | 対処 |
|---|---|---|
| Annular ring（SW センター穴 ×16） | NPTH パッドの `size` を小数点以下 3 桁に丸めたため穴径 3.9878 より 0.0002 mm 大きくなり、Gerber に銅の円が残った | `scripts/generate_agentpad_rev1.py` の `pad_th()` で NPTH のサイズを drill と同値にした（全リビジョン共通） |
| Solder mask opening exposing trace（1 件） | SW3 ソケットパッドのマスク開口すれすれを同じネット（K3）のトレースが通っていた。実害なし | 引き込み経路をパッドの上側から入るように変更（SINGLE_PCB 限定） |
| Silkscreen to hole（14 件） | MCU ピンラベル `GND` が GND ビア `(21, 4)` の真下にあった。**JLC は文字の 1 画ごとに 1 件と数える**ので、14 件でも原因は 1 か所のことが多い | 左側ラベルの X 位置をずらした（−12.8 だと別のシルクと重なって DRC 違反になったので −12.0） |
| tht to smd（rev3 で 12 件） | 直挿し用 PTH と ホットスワップ SMD パッドが 1.38 mm。基準は 2.03 mm 未満がエラー | JLC に実装（PCBA）を頼む場合だけ関係する。手はんだなら無視してよい |
| Silkscreen line width（警告 100 件） | 線幅 0.15 mm が推奨下限付近 | 警告のみ。発注可能 |

判定基準の目安: Silkscreen to hole は 0.13 mm 未満が Danger、0.13〜0.18 mm が Warning。

### シルクと穴の距離を手元で再現する

JLCDFM の件数だけでは原因の箇所がわかりにくいとき、同梱スクリプトで Gerber とドリルから距離を計算する。

```sh
.venv/bin/python .claude/skills/jlcdfm-check/silk_hole.py gerber/rev2_single
```

0.18 mm 未満の組み合わせを `Danger` / `Warning` で出力する（シルクの 1 画ごとではなく、穴ごとに最小距離を出す）。修正後に再生成したディレクトリにも同じように実行して、0 件になることを JLCDFM に上げる前に確認できる。

## 手順 3: 修正 → 再確認ループ

AGENTS.md のとおり Gerber や ZIP は手で編集せず、生成スクリプトを直す。

1. `scripts/generate_agentpad_rev1.py` を修正する。特定リビジョンだけに効かせたい場合は `REV` / `SINGLE_PCB` の条件をつけ、他リビジョンの出力を変えない。
2. scratchpad に再生成する:
   ```sh
   AGENTPAD_OUT=<scratchpad>/rev2_build .venv/bin/python scripts/generate_agentpad_rev2.py
   ```
3. `<OUT>/docs/VALIDATION_REV*.md` で geometry checks が PASS、DRC が違反 0 件・未接続 0 件であることを確認する。DRC 違反は `<OUT>/docs/drc/*-drc.json` の `violations` で中身を見る。
4. 既存の出力と diff を取り、変わったのが意図した箇所だけか確認する（`G04` / `%TF` / `CreationDate` の行は除外して比較する）。
5. 再生成した `<OUT>/manufacturing/agentpad_<rev>_gerber.zip` を手順 1 で JLCDFM にかけ、Danger が消えたことを確認する。
6. **リポジトリへの上書きはユーザーに確認してから行う**（この checkout は git 管理されていないので戻せない）。上書き前に、内容が異なるファイルだけを scratchpad の `<rev>_backup_<日付>/` にコピーし、`cmp -s` で差分のあるファイルだけを上書きする。`scripts/` 配下のコピーは上書きしない。
7. 上書き後に `scripts/run_kicad_drc.sh <rev>` を実行し、違反 0 件を確認する。
8. 最終報告では、DFM の修正前と修正後の比較表、viewer の URL、更新したファイル、バックアップの場所、残っている警告とその影響を伝える。

## 発注オプション（聞かれた場合）

`docs/JLCPCB_ORDER_<REV>.md` と、Gerber に同梱された `*-job.gbrjob` の `GeneralSpecs` / `DesignRules` を読んでから答える。AgentPad の標準は次のとおり。

- FR-4、2 層、1.6 mm、1 oz、Different Design 1、Delivery Format は Single PCB（panel ZIP の場合はドキュメントに従う）
- Surface Finish は HASL（手はんだ前提）。ソケットパッドを平らにしたいなら ENIG
- Via Covering は Tented。Mark on PCB は Remove Mark を推奨（表面にラベルが多いため）
- PCBA と Stencil は不要（すべて手はんだ）
- アップロード後に Gerber Viewer で外形サイズ・NPTH・裏面 SMD パッド・取付穴を確認してもらう
