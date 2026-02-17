from pathlib import Path
from typing import Never
from enum import Enum
import argparse
import sys
import shutil
import subprocess


# Nord color palette (ANSI escape codes)
class Nord(Enum):
    FROST2 = "\033[38;2;129;161;193m"
    PURPLE = "\033[38;2;180;142;173m" 
    RED = "\033[38;2;191;97;106m"
    YELLOW = "\033[38;2;235;203;139m"
    GREEN = "\033[38;2;163;190;140m"
    RESET = "\033[0m"

    def __str__(self) -> str:
        return self.value


HOME: Path = Path.home()
TEMPDIRS: list[Path] = [HOME / "temps"]  # template directories
DEFAULT_TEMP: Path = HOME / "temps" / "typsttemp" / "template.typ"


def pretty(path: Path) -> str:
    path = path.resolve()
    home = HOME.resolve()

    # Trim paths to just last 2 parts for printing 
    try:
        rel = path.relative_to(home)
        parts = rel.parts
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        elif parts:
            return f"{parts[-1]}"
        return "~"
    except ValueError:
        parts = path.parts
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return str(path)


def eprint(msg: str) -> None:
    print(f"{Nord.YELLOW}{msg}{Nord.RESET}", file=sys.stderr)


# fp reference 
def bottomtype(msg: str, code: int = 1) -> Never:
    if msg:
        print(f"{Nord.RED}{msg}{Nord.RESET}", file=sys.stderr)
    sys.exit(code)


def expand_path(p: str | Path) -> Path:
    return Path(p).expanduser().resolve()


def looks_like_path(s: str) -> bool:
    return ("/" in s) or ("\\" in s)


def resolve_temppath(tempstr: str) -> Path:
    """Resolving template argument
    First checks for absolute path, then checks for directory in TEMPDIRS, then file in TEMPDIRS
    Returns directory path or file path
    """
    tempstr = tempstr.strip()
    temppath: Path = Path(tempstr)
    isabs: bool = temppath.is_absolute()

    if isabs: # check absolute path first
        if temppath.exists():
            return temppath
        else:
            bottomtype(f"Error: Could not resolve absolute path {temppath}")
    else: # check relative path 
        local = expand_path(tempstr)
        if local.exists():
            return local
    
    # look through TEMPDIRS
    dmatches: list[Path] = []
    fmatches: list[Path] = []
    for tempdir in TEMPDIRS:
        if not tempdir.exists():
            eprint(f"Warning: Template directory {tempdir} does not exist")
            continue

        tpath: Path = tempdir / tempstr
        if tpath.exists() and tpath.is_dir():  # look for directory first
            dmatches.append(tpath)
            continue
        elif looks_like_path(tempstr) and tpath.is_file():  # look for file with path
            fmatches.append(tpath)
            continue
        else:  # recursively searches for standalone file 
            for f in tempdir.rglob("*"):
                if f.is_file() and f.name == tempstr:
                    fmatches.append(f)

    if (len(dmatches) + len(fmatches)) > 1:
        eprint("Multiple matches found:\n")
        eprint("Directories:")
        for d in dmatches:
            eprint(f"  {d}")
        eprint("\nFiles:")
        for f in fmatches:
            eprint(f"  {f}")
        bottomtype("")
    elif dmatches:
        return dmatches[0]
    elif fmatches:
        return fmatches[0]
    bottomtype("Error: Unable to resolve template file")


def find_tempfile(tempdir: Path) -> Path:
    """Find template file given directory path"""
    matches = list(filter(lambda p: p.is_file(), tempdir.rglob("template.*")))

    if len(matches) == 0:
        bottomtype(f"Error: No template.* files found in {tempdir}")
    elif len(matches) > 1:
        eprint(f"Error: Multiple template.* files found in {tempdir}:")
        for match in matches:
            eprint(f"  {match}")
        bottomtype("Please specify which template to use with -t flag")
    return matches[0]


def copy_no_a(temppath: Path, target: Path) -> None:
    """Copy while renaming template to target file/directory; overwrites
    Takes in filePath, target can be directory or file
    """
    if (target.exists() and target.is_file()) or target.suffix:  # file target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temppath, target)
        print(f"{Nord.PURPLE}Copied {Nord.FROST2}{pretty(temppath)}{Nord.PURPLE} to {Nord.FROST2}{pretty(target)}{Nord.RESET}")
        return
    else:  # directory target
        target.mkdir(parents=True, exist_ok=True)
        ext = temppath.suffix
        base_name = target.name or target.parent.name or temppath.stem
        new_file = target / f"{base_name}{ext}"
        shutil.copy2(temppath, new_file)
        print(f"{Nord.PURPLE}Copied {Nord.FROST2}{pretty(temppath)}{Nord.PURPLE} to {Nord.FROST2}{pretty(new_file)}{Nord.RESET}")


def copy_a(temppath: Path, target: Path) -> None:
    """Copy contents of entire directory/file, no rename; overwrites target
    Target must be a directory
    """

    target.mkdir(parents=True, exist_ok=True)
    if temppath.is_dir():
        for item in temppath.iterdir():
            dest = target / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
    else:
        eprint("Warning: Using -a on file source")
        shutil.copy2(temppath, target)


def list_fzf_candidates() -> list[Path]:
    """
    List options in TEMPDIRS
    """
    out: list[Path] = []
    for d in TEMPDIRS:
        if not d.exists():
            eprint(f"Warning: Template directory {d} does not exist")
            continue
        for p in d.iterdir():
            out.append(p)
    return out


def fzf_pick(candidates: list[Path]) -> Path:
    """
    Start the fzf process, pipe it back 
    """
    if not candidates:
        bottomtype("Error: No templates found in template directories.")

    proc = subprocess.run(
        ["fzf", "--prompt", "template> "],
        input="\n".join(str(p) for p in candidates),
        text=True,
        capture_output=True,
    )

    if proc.returncode != 0:
        bottomtype("Aborted.")

    return expand_path(proc.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="For copying homework templates")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-t",
        "--template",
        default=None,
        help=f"Template name or path. Searches in: {', '.join(map(str, TEMPDIRS))}",
    )
    group.add_argument(
        "-f",
        "--fuzzy",
        action="store_true",
        help=f"Pick a template via fzf from: {', '.join(map(str, TEMPDIRS))}",
    )
    parser.add_argument(
        "-a",
        "--all",
        help="Copy all contents of template directory/file (no rename). Target(s) must be directories.",
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
        [Path.cwd()] if not args.targets else [expand_path(t) for t in args.targets]
    )

    # Resolve template (file or directory)
    if args.fuzzy:
        resolved: Path = fzf_pick(list_fzf_candidates())
    else:
        resolved = resolve_temppath(args.template or str(DEFAULT_TEMP))
    print(f"{Nord.PURPLE}Using template: {Nord.FROST2}{pretty(resolved)}{Nord.RESET}")

    # Guard: avoid copying a directory template into itself or vice versa
    if resolved.is_dir():
        troot = resolved.resolve()
        for tgt in targets:
            trg = tgt.resolve()
            # Check if target is inside template
            if troot == trg or troot in trg.parents:
                bottomtype(
                    f"Error: Target {tgt} is inside template directory {resolved}. Refusing to copy."
                )
            # Check if template is inside target
            if trg in troot.parents:
                bottomtype(
                    f"Error: Template {resolved} is inside target directory {tgt}. Refusing to copy."
                )

    # -a mode: copy the template path "as-is" into each target directory
    if args.all:
        for tgt in targets:
            if tgt.exists() and not tgt.is_dir():
                bottomtype(f"Error: Target {tgt} is not a directory (required for -a).")
            copy_a(resolved, tgt)
            print(f"{Nord.PURPLE}Copied contents of {Nord.FROST2}{pretty(resolved)}{Nord.PURPLE} to {Nord.FROST2}{pretty(tgt)}{Nord.RESET}")
        print(f"{Nord.GREEN}Done!{Nord.RESET}")
        return

    # Default mode: copy a single template file into targets (with rename rules)
    template_file: Path = find_tempfile(resolved) if resolved.is_dir() else resolved
    for tgt in targets:
        copy_no_a(template_file, tgt)

    print(f"{Nord.GREEN}Done!{Nord.RESET}")


if __name__ == "__main__":
    main()
