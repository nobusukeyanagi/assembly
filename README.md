# ASSEMBLY | 朝礼モニター

朝礼向けの1920×1080固定レイアウト。大きな日付と4つの情報枠（競輪、オートレース、SODA対象ボートレース、森且行選手の出走予定）を表示します。画面サイズに応じて同じ比率で縮小表示します。

## 公開URL

https://nobusukeyanagi.github.io/assembly/

**初回だけ** リポジトリの [Settings → Pages](https://github.com/nobusukeyanagi/assembly/settings/pages) にある **Build and deployment > Source** を **GitHub Actions** に変更してください。その後、[Actions → 朝礼情報更新・本番公開](https://github.com/nobusukeyanagi/assembly/actions/workflows/refresh.yml) から `Run workflow` を実行します。初回の Pages 有効化は `GITHUB_TOKEN` だけでは行えません。

## 自動更新

- 毎日 **01:10 JST**（cron は UTC 16:10）。GitHub Actions の実行開始には遅延があり得ます。
- `main` ブランチの HTML / CSS / JS / 収集スクリプトの変更時も自動実行し、公開サイトを更新します。
- 手動更新: **Actions → 朝礼情報更新・本番公開 → Run workflow**。
- 生成データ: `data/today.json`。画面は10分ごと、再表示時にも当日のデータを取得し直します。
- 昨日以前のデータを開催情報として表示しません。取得失敗は「情報を確認中」と表示し、推測で埋めません。

## 公開画面の表示切り替え（当日／日付指定）

[Actions → 朝礼情報更新・本番公開](https://github.com/nobusukeyanagi/assembly/actions/workflows/refresh.yml) → **Run workflow** から実行します。

- **表示方法**：`当日` または `日付指定` を選択します。初期選択は **`日付指定`** です。
- **日付指定**の場合は日付を `YYYY-MM-DD` で入力します。初期値 `2026-11-23`。
- **当日**の場合、日付入力の値は処理上**無効（無視）**になります。GitHub Actionsの標準フォームは選択内容に応じた入力欄の非活性化に対応していないため、画面上の入力欄は操作できます。
- 実行後、通常の公開URL（https://nobusukeyanagi.github.io/assembly/）の画面自体が切り替わります。画像出力ではありません。
- 日付指定の場合は公開日程の取得処理をその日付に対して実行し、`data/selected.json` を作成します。架空の開催場・サンプルデータは使用しません。過去・未来の日程を取得できない情報源では空欄や取得エラー表示になります。
- 日付指定中は画面右上に「日付指定表示」と示します。
- 元に戻す場合は **Run workflow → 当日** を選択します。
- 選択モードは `data/display.json` に保存し、毎日の自動更新をまたいでも保持します。`data/today.json` は引き続き日次更新します。

## 取得元と注意点

| 表示項目 | 取得元 |
|---|---|
| 競輪 | [KEIRIN.JP公式開催日程](https://keirin.jp/sp/raceschedule) |
| オートレース | [WINTICKET月間開催日程](https://www.winticket.jp/autorace/schedules/)（[AUTORACE.JP](https://autorace.jp/calendar/)の個別出走表は開催日程判定に使用できないため補完） |
| SODA対象場 | [SODA](https://so-da.jp/aud/top) の対応場を、[BOAT RACE公式開催日程](https://www.boatrace.jp/owpc/pc/race/index) と照合 |
| 森且行選手 | [WINTICKET選手プロフィール](https://www.winticket.jp/autorace/autoracer/2529/) と、当日開催期間中は WINTICKET の出走表 |

**SODA欄は「SODA対応場で開催されるレース場」です。SODAでそのレースが配信されることを保証しません。**

森選手は当日出走が出走表で確かめられたときのみ場名・R番号を表示します。あっせん日程しか確認できない場合は「本日の出走R確認中」または「次回あっせん予定」と表示します。出走取消・変更の可能性があります。

**Gamboo** はアクセス確認画面等のため自動取得元には利用せず、各競技の日程ソースを優先しています。

## 構成

- `index.html` 表示画面
- `styles.css` 表示スタイル
- `app.js` JSON読込、日付チェック、画面描画と自動更新
- `scripts/update.py` 日程取得・検証・JSON保存
- `tests/test_update.py` 基本単体テスト
- `.github/workflows/refresh.yml` 01:10 JST自動収集と Pages 本番公開

ローカルで試す場合: `pip install -r requirements.txt` → `python -m unittest discover -s tests` → `python scripts/update.py` → `python -m http.server 8000`。
