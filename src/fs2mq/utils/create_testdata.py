#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import random
import stat
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# =============================
# Helpers
# =============================

def _rand_text(n: int, rng: random.Random) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(rng.choices(alphabet, k=n))


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_text_file(p: Path, size_bytes: int, rng: random.Random) -> None:
    # text file of roughly size_bytes (ASCII)
    p.write_text(_rand_text(size_bytes, rng))


def _count_regular_files(root: Path) -> int:
    c = 0
    for x in root.rglob("*"):
        try:
            if x.is_file() and not x.is_symlink():
                c += 1
        except OSError:
            # broken symlink etc.
            continue
    return c


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _info(msg: str) -> None:
    print(f"[INFO] {msg}")


# =============================
# Profiles
# =============================

@dataclass(frozen=True)
class LightConfig:
    depth: int = 1
    dirs_per_level: int = 2
    files_per_dir: int = 3
    file_size: int = 64


@dataclass(frozen=True)
class DeepConfig:
    depth: int = 6
    dirs_per_level: int = 2
    target_files: int = 128
    file_size: int = 64


@dataclass(frozen=True)
class EdgeConfig:
    include_symlink: bool = True
    include_broken_symlink: bool = True
    include_fifo: bool = True
    include_no_permission_dir: bool = True
    include_no_permission_file: bool = True
    include_weird_names: bool = True


# -----------------------------
# light case
# -----------------------------

def create_light(base: Path, seed: int) -> None:
    cfg = LightConfig()
    rng = random.Random(seed)

    _info(f"Creating LIGHT profile at {base}")
    _safe_mkdir(base)

    # simple shallow tree
    for d0 in range(cfg.dirs_per_level):
        dpath = base / f"level-0-dir-{d0}"
        _safe_mkdir(dpath)
        for i in range(cfg.files_per_dir):
            _write_text_file(dpath / f"file-{d0}-{i}.txt", cfg.file_size, rng)

    _info(f"Created ~{_count_regular_files(base)} regular files")


# -----------------------------
# deep case
# -----------------------------

def create_deep(base: Path, seed: int, depth: int, target_files: int, file_size: int) -> None:
    cfg = DeepConfig(depth=depth, target_files=target_files, file_size=file_size)
    rng = random.Random(seed)

    _info(f"Creating DEEP profile at {base}")
    _safe_mkdir(base)

    # We want exactly target_files regular files, while also creating a deep structure.
    # Strategy:
    # - create a single deep "spine" directory path to guarantee depth
    # - then distribute files across levels to hit target_files deterministically
    spine: list[Path] = [base]
    for lvl in range(1, cfg.depth + 1):
        p = spine[-1] / f"level-{lvl}"
        _safe_mkdir(p)
        spine.append(p)

    # Deterministic distribution: round-robin files across levels
    created = 0
    level_count = len(spine)
    while created < cfg.target_files:
        lvl = created % level_count
        d = spine[lvl]
        # file name encodes level and sequence
        fname = f"file-l{lvl:02d}-{created:04d}.txt"
        _write_text_file(d / fname, cfg.file_size, rng)
        created += 1

    _info(f"Created exactly {created} regular files")
    _info(f"Deepest directory: {spine[-1]}")


# -----------------------------
# edge case
# -----------------------------

def create_edge(base: Path, seed: int) -> None:
    cfg = EdgeConfig()
    rng = random.Random(seed)

    _info(f"Creating EDGE profile at {base}")
    _safe_mkdir(base)

    edge = base / "edge-cases"
    _safe_mkdir(edge)

    # 1) Weird filenames (cross-platform-ish)
    if cfg.include_weird_names:
        weird_dir = edge / "weird-names"
        _safe_mkdir(weird_dir)
        candidates = [
            "space name.txt",
            "unicode-äöü.txt",
            "brackets-[x].txt",
            "semi;colon.txt",
            "comma,name.txt",
        ]
        for name in candidates:
            try:
                _write_text_file(weird_dir / name, 32, rng)
            except OSError as e:
                _warn(f"Could not create weird filename '{name}': {e}")

    # 2) Permission issues
    if cfg.include_no_permission_dir:
        np_dir = edge / "no-permission-dir"
        _safe_mkdir(np_dir)
        # put a file inside first
        _write_text_file(np_dir / "inside.txt", 32, rng)
        try:
            # remove all permissions
            np_dir.chmod(0)
        except PermissionError as e:
            _warn(f"Could not chmod(0) for {np_dir}: {e}")
        except OSError as e:
            _warn(f"chmod failed for {np_dir}: {e}")

    if cfg.include_no_permission_dir:
        np_dir = edge / "no-permission-dir"

        # If it exists from a previous run with chmod(0), restore permissions first.
        if np_dir.exists():
            try:
                np_dir.chmod(0o700)
            except OSError as e:
                _warn(f"Could not restore permissions for {np_dir}: {e}")

        _safe_mkdir(np_dir)

        # Try creating a file inside; if we cannot, warn and continue.
        try:
            _write_text_file(np_dir / "inside.txt", 32, rng)
        except PermissionError as e:
            _warn(f"Could not write inside {np_dir} (permission): {e}")

        # Finally, remove permissions to simulate access denied during scan
        try:
            np_dir.chmod(0)
        except OSError as e:
            _warn(f"Could not chmod(0) for {np_dir}: {e}")

    # 3) Symlink cases
    if cfg.include_symlink:
        target = edge / "weird-names" / "space name.txt"
        link = edge / "symlink-to-space-name"
        try:
            if link.exists() or link.is_symlink():
                link.unlink()
            os.symlink(target, link)
        except (OSError, NotImplementedError) as e:
            _warn(f"Could not create symlink {link} -> {target}: {e}")

    if cfg.include_broken_symlink:
        broken_target = edge / "does-not-exist.txt"
        broken_link = edge / "broken-symlink"
        try:
            if broken_link.exists() or broken_link.is_symlink():
                broken_link.unlink()
            os.symlink(broken_target, broken_link)
        except (OSError, NotImplementedError) as e:
            _warn(f"Could not create broken symlink {broken_link}: {e}")

    # 4) Special files (FIFO) on Unix
    if cfg.include_fifo:
        fifo_path = edge / "fifo-special"
        try:
            if fifo_path.exists():
                fifo_path.unlink()
            os.mkfifo(fifo_path)
        except AttributeError:
            _warn("os.mkfifo is not available on this platform; skipping FIFO creation.")
        except PermissionError as e:
            _warn(f"Could not create FIFO {fifo_path} (permission): {e}")
        except OSError as e:
            _warn(f"Could not create FIFO {fifo_path}: {e}")

    _info(f"Regular files currently visible: ~{_count_regular_files(base)}")
    _info("NOTE: Some edge cases may be skipped depending on OS/filesystem permissions.")


# ============================
# CLI
# ============================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate test directory structures for fs2mq.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Light profile (default)
  uv run python src/utils/create_testdata.py ./data

  # Deep directory tree with exactly 500 files
  uv run python src/utils/create_testdata.py ./data \\
      --profile deep \\
      --depth 8 \\
      --target-files 500

  # Edge cases (symlinks, permissions, FIFO, weird filenames)
  uv run python src/utils/create_testdata.py ./data \\
      --profile edge

Notes:
  - 'path' is the base directory where test data will be created.
  - The deep profile guarantees exactly --target-files regular files.
  - Some edge cases may be skipped depending on OS/filesystem permissions.
""",
    )        
    
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="Base directory where test data will be created",
    )
    parser.add_argument(
        "--profile",
        choices=["light", "deep", "edge"],
        default="light",
        help="Test data profile to generate (default: light)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic content (default: 42)",
    )

    # deep-specific knobs
    parser.add_argument(
        "--depth",
        type=int,
        default=6,
        help="Depth for the deep profile (default: 6)",
    )
    parser.add_argument(
        "--target-files",
        type=int,
        default=128,
        help="Total number of files for the deep profile (default: 128)",
    )
    parser.add_argument(
        "--file-size",
        type=int,
        default=64,
        help="Approx size of each generated text file in bytes (default: 64)",
    )

    args = parser.parse_args()

    # If called without a path, show help and exit cleanly.
    if args.path is None:
        parser.print_help()
        return

    base = args.path.resolve()
    profile = args.profile

    if profile == "light":
        create_light(base, seed=args.seed)
    elif profile == "deep":
        create_deep(
            base,
            seed=args.seed,
            depth=args.depth,
            target_files=args.target_files,
            file_size=args.file_size,
        )
    elif profile == "edge":
        create_edge(base, seed=args.seed)
    else:
        raise RuntimeError(f"Unknown profile: {profile}")

    _info("Done.")


if __name__ == "__main__":
    main()

# -----------------------------
# END
# ============================
