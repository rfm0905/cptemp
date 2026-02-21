import argparse
import shutil
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from typing import Never


# Nord color palette (ANSI escape codes)
class NORD(StrEnum):
    FILE = "\033[38;2;129;161;193m"
    ACCENT = "\033[38;2;180;142;173m"
    ERROR = "\033[38;2;191;97;106m"
    WARNING = "\033[38;2;235;203;139m"
    SUCCESS = "\033[38;2;163;190;140m"
    RESET = "\033[0m"

    def __str__(self) -> str:
        return self.value


def eprint(msg: str) -> None:
    print(f"{NORD.WARNING}{msg}{NORD.RESET}", file=sys.stderr)


# fp reference
def bottomtype(msg: str, code: int = 1) -> Never:
    if msg:
        print(f"{NORD.ERROR}{msg}{NORD.RESET}", file=sys.stderr)
    sys.exit(code)


HOME: Path = Path.home()
TEMPDIRS: list[Path] = [HOME / "temps"]  # template directories
DEFAULT_TEMP: Path = HOME / "temps" / "typsttemp" / "template.typ"


def looks_like_path(s: str) -> bool:
    return ("/" in s) or ("\\" in s)


def pretty_path(path: Path, color: NORD = NORD.FILE) -> str:
    """Pretty prints paths. Uses last 2 parts (i.e 'foo/bar/abc' becomes 'bar/abc')"""
    path = path.expanduser().resolve()
    try:
        rel = path.relative_to(HOME)
        if not rel.parts:
            return "~"
        parts = rel.parts[-2:]
    except ValueError:
        parts = path.parts[-2:]

    return f"{color}{Path(*parts)}{NORD.RESET}"


def find_tempfile(searchdir: Path) -> Path:
    """
    Searches single template file (template or template.*) within a directory
    Exits with error on multiple or no matches
    """
    matches: list[Path] = [p for p in searchdir.rglob("template*") if p.is_file()]
    if len(matches) == 0:
        bottomtype(f"Error: No template.* files found in {pretty_path(searchdir)}")
    elif len(matches) > 1:
        eprint(f"Error: Multiple template.* files found in {pretty_path(searchdir)}:")
        for match in matches:
            eprint(f"  {match}")
        bottomtype("Please specify which template to use with -t flag")
    return matches[0]


def search_tempdir(tempstr: str, tempdir: Path) -> tuple[list[Path], list[Path]]:
    """
    Searches a template directory for given name or path, returning directory and file matches
    """
    if not tempdir.exists():
        eprint(
            f"Warning: Template directory {pretty_path(tempdir, color=NORD.ACCENT)}{NORD.WARNING} does not exist, skipping search to next template directory"
        )
        return [], []

    tpath = tempdir / tempstr
    if tpath.is_dir():  # find directory matches
        return [tpath], []
    if looks_like_path(tempstr) and tpath.is_file():  # find file path matches
        return [], [tpath]
    else:  # Search for stand-alone files with name
        return [], [p for p in tempdir.glob(tempstr) if p.is_file()]


def resolve_template(tempstr: str) -> Path:
    """
    Resolve the template argument by checking absolute/relative paths, then TEMDPIRS.
    """
    tempstr = tempstr.strip()
    temppath: Path = Path(tempstr).expanduser().resolve()

    # check absolute or relative path first
    if temppath.exists():
        return temppath

    # search TEMPDIRS
    dmatches: list[Path] = []
    fmatches: list[Path] = []
    for ds, fs in (search_tempdir(tempstr, td) for td in TEMPDIRS):
        dmatches.extend(ds)
        fmatches.extend(fs)

    if len(dmatches) == 1:
        return dmatches[0]
    elif (len(dmatches) + len(fmatches)) > 1:
        eprint("Multiple matches found:\n")
        eprint("Directories:")
        for d in dmatches:
            eprint(f"  {d}")
        eprint("\nFiles:")
        for f in fmatches:
            eprint(f"  {f}")
        bottomtype("Specify exact template with -t flag next time")
    elif fmatches:
        return fmatches[0]
    bottomtype(f"Error: Unable to resolve template directory \"{NORD.ACCENT}{tempstr}{NORD.ERROR}\" or file")


def copy_rename(temploc: Path, targets: list[Path]) -> None:
    """
    Copies template file into each target.
    If target is a directory, renames template file to match the directory name.
    Overwrites existing files on conflict
    """
    temppath = find_tempfile(temploc) if temploc.is_dir() else temploc
    for target in targets:
        if (target.exists() and target.is_file()) or target.suffix:  # file target
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(temppath, target)
            print(
                f"{NORD.ACCENT}Copied {pretty_path(temppath)}{NORD.ACCENT} to {pretty_path(target)}"
            )
        else:  # directory target
            target.mkdir(parents=True, exist_ok=True)
            ext = temppath.suffix
            base_name = target.name or target.parent.name or temppath.stem
            dest = target / f"{base_name}{ext}"
            shutil.copy2(temppath, dest)
            print(f"{NORD.ACCENT}Copied {pretty_path(temppath)}{NORD.ACCENT} to {pretty_path(dest)}")


def copy_norename(temppath: Path, targets: list[Path]) -> None:
    """
    Copy template contents as-is into each target. Requires directory targets
    If template is a file, copy it into each target directory with original name
    If template is a directory, merge its content into each target directory
    Overwrites on conflicts.
    """

    if not temppath.exists():
        bottomtype(
            f"Error: Could not resolve template path {NORD.ACCENT}{temppath}{NORD.ERROR} to existing file or directory"
        )

    for target in targets:
        if target.exists() and target.is_file():
            eprint(
                f"Error: -a requires a directory target, found file {NORD.ACCENT}{target}{NORD.ERROR}. Skipping to next target"
            )
            continue

        target.mkdir(parents=True, exist_ok=True)
        if temppath.is_file():
            target_path = target / temppath.name
            if target_path.exists() and target_path.is_dir():
                shutil.rmtree(target_path)
            shutil.copy2(temppath, target_path)
            print(
                f"{NORD.ACCENT}Copied {pretty_path(temppath)}{NORD.ACCENT} to {pretty_path(target)}"
            )
        elif temppath.is_dir():
            shutil.copytree(temppath, target, dirs_exist_ok=True)
            print(
                f"{NORD.ACCENT}Copied contents of {pretty_path(temppath)}{NORD.ACCENT} to {pretty_path(target)}"
            )
        else:
            bottomtype(
                f"Error: Could not resolve template path {NORD.ACCENT}{temppath}{NORD.ERROR} to existing file or directory"
            )


def list_fzf_candidates() -> list[Path]:
    """List immediate entries in all template directories."""
    out: list[Path] = []
    for tempdir in TEMPDIRS:
        if not tempdir.exists():
            eprint(f"Warning: Template directory {pretty_path(tempdir, color=NORD.ACCENT)}{NORD.WARNING} does not exist")
            continue
        out.extend(p for p in tempdir.iterdir())
    return out


def fzf_pick(candidates: list[Path]) -> Path:
    """Run fzf over candidate paths and return the selected path."""
    if not candidates:
        bottomtype("Error: No templates found in template directories.")

    try:
        proc = subprocess.run(
            ["fzf", "--prompt", "template> "],
            input="\n".join(str(p) for p in candidates),
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        bottomtype("Error: `fzf` not on PATH or not installed.")

    if proc.returncode != 0:
        bottomtype("Aborted.")
    return Path(proc.stdout.strip()).expanduser().resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="For copying homework templates")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-t",
        "--template",
        default=None,
        help=f"Template name or path. If not path, searches in: {', '.join(map(str, TEMPDIRS))}",
    )
    group.add_argument(
        "-f",
        "--fuzzy",
        action="store_true",
        help=f"Pick a template via fzf from: {', '.join(map(str, TEMPDIRS))}",
    )
    parser.add_argument(
        "-a",
        "--as-is",
        help="Copy template contents as-is (no rename). Target(s) must be directories",
        action="store_true",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Target directories or files (default: current directory)",
    )
    args = parser.parse_args()

    # Resolve targets to Paths
    targets: list[Path] = (
        [Path.cwd()]
        if not args.targets
        else [Path(t).expanduser().resolve() for t in args.targets]
    )

    # Resolve template (file or directory)
    if args.fuzzy:
        temppath: Path = fzf_pick(list_fzf_candidates())
    else:
        temppath = resolve_template(args.template or str(DEFAULT_TEMP))
    print(f"{NORD.ACCENT}Using template: {pretty_path(temppath)}")

    # Guard: avoid copying a directory template into itself
    if temppath.is_dir():
        temppath = temppath.resolve()
        for target in targets:
            if temppath == target or temppath in target.parents:
                bottomtype(
                    f"Error: Target {NORD.ACCENT}{target}{NORD.ERROR} is inside template directory {NORD.ACCENT}{temppath}{NORD.ERROR}. Refusing to copy"
                )

    copy_norename(temppath, targets) if args.as_is else copy_rename(temppath, targets)
    print(f"{NORD.SUCCESS}Done!{NORD.RESET}")


if __name__ == "__main__":
    main()
