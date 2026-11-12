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

## 日付指定プレビュー（本番に影響なし）

[Actions → 日付指定プレビュー（サンプルデータ）](https://github.com/nobusukeyanagi/assembly/actions/workflows/preview.yml) → **Run workflow** から実行します。

- `date`：プレビュー日付（YYYY-MM-DD、初期値 `2026-11-23`）
- `keirin_count`：競輪開催場の**テスト用**場数（0～12、初期値 `12`）
- ブラウザーは日付を指定日の12:00 JSTに固定して、1920×1080で描画します。祝日表示もその日付に応じて確認できます。
- テスト結果は実行ページの **Artifacts → `preview-日付-keirin場数`** に保存されます。PNG画面、検証レポート、投入したサンプルデータを同梱します。
- オート3場、SODA8場、森選手の出走予定は画面確認用の架空データです。競輪の開催場も同様で、**指定日の実開催情報ではありません**。
- 競輪12場のときは3行、8場以下は2行構成を検証します。
- **本番の日次データ `data/today.json` は変更せず、GitHub Pagesにもデプロイしません。** Actionsの権限は読み取りのみです。
- このワークフローを追加・修正した直後は、初期値（11月23日・競輪12場）で自動テストを実行します。

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
