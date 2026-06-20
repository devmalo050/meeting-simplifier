#!/usr/bin/env python3
# scripts/config.py
# 회의록 저장 폴더 등 플러그인 런타임 설정을 $MS_DATA_DIR/config.json에 보관.
# 사용법: python config.py --show | --set <PATH> | --reset  → JSON 결과 stdout
import sys
import os
import json
import argparse
from pathlib import Path

DEFAULT_OUTPUT_DIR = "~/Documents/meetings"


def data_dir():
    env = os.environ.get("MS_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "plugins" / "data" / "meeting-simplifier-meeting-simplifier"


def config_path():
    return data_dir() / "config.json"


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, ValueError, OSError):
        pass
    return {}


def save_config(cfg):
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_output_dir():
    return load_config().get("output_dir")


def set_output_dir(path):
    resolved = str(Path(path).expanduser().absolute())
    Path(resolved).mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg["output_dir"] = resolved
    save_config(cfg)
    return resolved


def unset_output_dir():
    cfg = load_config()
    cfg.pop("output_dir", None)
    save_config(cfg)


def effective_output_dir():
    return get_output_dir() or DEFAULT_OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", action="store_true")
    g.add_argument("--set", metavar="PATH")
    g.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    try:
        if args.show:
            configured = get_output_dir()
            print(json.dumps({
                "ok": True,
                "output_dir": effective_output_dir(),
                "is_default": configured is None,
            }, ensure_ascii=False))
        elif args.set:
            resolved = set_output_dir(args.set)
            print(json.dumps({"ok": True, "output_dir": resolved}, ensure_ascii=False))
        else:
            unset_output_dir()
            print(json.dumps({
                "ok": True,
                "output_dir": DEFAULT_OUTPUT_DIR,
                "is_default": True,
            }, ensure_ascii=False))
    except OSError as e:
        print(json.dumps({"ok": False, "message": f"해당 경로를 사용할 수 없습니다: {e}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
