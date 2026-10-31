#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 CMIS skill：遍历 cmis-skill/ 生成根目录 cmis-skill.skill（zip）。
排除 history/ 与 __pycache__。打包后自动做一致性校验。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "cmis-skill")
OUT = os.path.join(ROOT, "cmis-skill.skill")
EXCLUDE_DIRS = {"history", "__pycache__", ".git"}


def build():
    if os.path.exists(OUT):
        os.remove(OUT)
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(SRC):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, SRC).replace("\\", "/")
                z.write(full, rel)
                n += 1
                print("  +", rel)
    print(f"\n打包完成：{OUT}  （{n} 个文件）")
    return n


def verify():
    """解包到临时目录，与源目录逐文件比对内容。"""
    print("\n一致性校验：")
    ok = True
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(OUT) as z:
            z.extractall(td)
        for dirpath, dirnames, filenames in os.walk(SRC):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in filenames:
                rel = os.path.relpath(os.path.join(dirpath, fn), SRC).replace("\\", "/")
                src = os.path.join(dirpath, fn)
                dst = os.path.join(td, rel.replace("/", os.sep))
                if not os.path.exists(dst):
                    print(f"  FAIL 包内缺失：{rel}")
                    ok = False
                    continue
                with open(src, "rb") as a, open(dst, "rb") as b:
                    if a.read() != b.read():
                        print(f"  FAIL 内容不一致：{rel}")
                        ok = False
        # 反向：包内不应有排除目录
        for dirpath, dirnames, filenames in os.walk(td):
            for d in dirnames:
                if d in EXCLUDE_DIRS:
                    print(f"  FAIL 包内含排除目录：{d}")
                    ok = False
    print("  OK 全部一致" if ok else "  存在不一致，请检查")
    return ok


if __name__ == "__main__":
    build()
    if not verify():
        sys.exit(1)
