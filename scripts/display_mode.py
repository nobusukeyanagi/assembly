#!/usr/bin/env python3
"""Persistent display selection used by GitHub Actions and by the published page."""
import argparse
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPLAY = ROOT / "data" / "display.json"
SELECTED = ROOT / "data" / "selected.json"

def valid_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        raise ValueError("日付はYYYY-MM-DD形式で入力してください")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("存在しない日付です: " + value) from exc

def config_for(mode: str, chosen_date: str = "") -> dict:
    if mode in ("当日", "today"):
        return {"mode": "today", "date": None}
    if mode in ("日付指定", "selected"):
        return {"mode": "selected", "date": valid_date(chosen_date)}
    raise ValueError("表示方法は「当日」か「日付指定」です")

def set_mode(mode: str, chosen_date: str = "", config_path: Path = DISPLAY, selected_path: Path = SELECTED) -> dict:
    config = config_for(mode, chosen_date)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    if config["mode"] == "today":
        selected_path.unlink(missing_ok=True)
    return config

def check(config_path: Path = DISPLAY, selected_path: Path = SELECTED) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("mode") == "today":
        if config.get("date") is not None:
            raise ValueError("当日表示には日付を指定できません")
    elif config.get("mode") == "selected":
        chosen = valid_date(config.get("date", ""))
        data = json.loads(selected_path.read_text(encoding="utf-8"))
        if data.get("date") != chosen or not isinstance(data.get("sections"), dict):
            raise ValueError("指定日と取得データの日付が一致しません")
    else:
        raise ValueError("表示モードの設定が不正です")
    return config

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("set","check"))
    parser.add_argument("--mode",default="当日")
    parser.add_argument("--date",default="")
    args=parser.parse_args()
    result=set_mode(args.mode,args.date) if args.action=="set" else check()
    print(json.dumps(result,ensure_ascii=False))
