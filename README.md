# ASSEMBLY | 朝礼モニター

朝礼用1920×1080画面。競輪・オートレース・SODA対象ボートレース場の当日開催、森且行選手の出走予定を表示します。

- 公開予定: https://nobusukeyanagi.github.io/assembly/
- 自動更新: 毎日01:10 JST（GitHub Actions）
- データ: `data/today.json`
- 更新プログラム: `scripts/update.py`
- 手動実行: Actions → 「朝礼情報更新・本番公開」→ Run workflow

**注意**: SODAはボートレース公式日程を「SODA対応場」に絞って表示します。SODA内のライブ配信を保証しません。Gambooはロボット確認画面のため、競輪・オートは公式サイトを自動取得元とします。取得失敗時には推測を表示しません。

出典: [競輪](https://keirin.jp/sp/raceschedule) / [オート](https://autorace.jp/) / [SODA](https://so-da.jp/aud/top) / [ボートレース](https://www.boatrace.jp/owpc/pc/race/index) / [森且行](https://sp.atrc.jp/racer/racerasseninfo/player_id/2529)

毎日1時10分はGitHub Actionsの起動予定時刻であり、公開完了時刻を保証するものではありません。

ローカル実行: `pip install -r requirements.txt && python scripts/update.py`。画面は `python -m http.server 8000` で確認。
