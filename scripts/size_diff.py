"""Tool to monitor LoC differences"""


# inspired by https://github.com/tinygrad/tinygrad/blob/master/sz.py

#####################################################################################################################################
#                                                           Module Setup                                                            #
#####################################################################################################################################

import itertools
import os
import sys
import token
import tokenize
from pathlib import Path
from typing import Any

from tabulate import tabulate  # type: ignore

TOKEN_WHITELIST = [token.OP, token.NAME, token.NUMBER, token.STRING]

#####################################################################################################################################
#                                                             Utilities                                                             #
#####################################################################################################################################


def is_docstring(tok: tokenize.TokenInfo) -> bool:
    """
    Return True if the token is a triple-quoted docstring.

    Args:
        tok (tokenize.TokenInfo): A tokenize.TokenInfo object.

    Returns:
        out (bool): True if the token is a docstring, False otherwise.
    """
    return tok.type == token.STRING and tok.string.startswith('"""') and tok.line.strip().startswith('"""')


def gen_stats(base_path: Path = Path(".")) -> list[list[Any]]:
    """
    Analyze Python files in the given directory and return per-file stats.

    Args:
        base_path (Path): The base directory to start the search from. Defaults to current directory.

    Returns:
        out (list[list[Any]]): A list of lists containing file name, line count, and token density (tokens per line).
    """
    stats = []
    for filepath in base_path.rglob("*.py"):
        with tokenize.open(filepath) as f:
            tokens = [tok for tok in tokenize.generate_tokens(f.readline) if tok.type in TOKEN_WHITELIST and not is_docstring(tok)]
        token_count = len(tokens)
        covered_lines = {ln for tok in tokens for ln in range(tok.start[0], tok.end[0] + 1)}
        line_count = len(covered_lines)
        if line_count > 0:
            relpath = filepath.relative_to(base_path).as_posix()
            density = token_count / line_count
            stats.append([relpath, line_count, density])
    return stats


def gen_diff(old_stats: list[list[Any]], new_stats: list[list[Any]]) -> list[list[Any]]:
    """
    Compare two stats lists and return diffs.

    Args:
        old_stats (list[list[Any]]): List of stats from the old version.
        new_stats (list[list[Any]]): List of stats from the new version.

    Returns:
        out (list[list[Any]]): A list of lists containing the file name, new line count, line delta, new density
    """
    diff_table = []
    # Lookup maps for old and new stats
    old_map = {row[0]: row for row in old_stats}
    new_map = {row[0]: row for row in new_stats}
    all_files = set(old_map) | set(new_map)  # Combine because some files may be added or deleted

    for fname in sorted(all_files):
        old_row = old_map.get(fname, [fname, 0, 0.0])
        new_row = new_map.get(fname, [fname, 0, 0.0])
        line_delta = new_row[1] - old_row[1]
        density_delta = new_row[2] - old_row[2]
        if line_delta != 0 or density_delta != 0:
            diff_table.append([fname, new_row[1], line_delta, new_row[2], density_delta])
    return diff_table


def display_diff(diff: int | float) -> str:
    """
    Format the difference for display.

    Args:
        diff (int | float): The difference value to format.

    Returns:
        out (str): A string representation of the difference, prefixed with '+' if positive.
    """
    return f"+{diff}" if diff > 0 else str(diff)


#####################################################################################################################################
#                                                           Main Function                                                           #
#####################################################################################################################################


def main() -> None:
    """Main function to parse command line arguments and generate stats or diffs."""
    args = sys.argv[1:]
    if len(args) == 2:
        headers = ["File", "Lines", "Diff", "Tokens/Line", "Token Density Diff"]
        old_stats = gen_stats(Path(args[0]))
        new_stats = gen_stats(Path(args[1]))
        table = gen_diff(old_stats, new_stats)
    else:
        headers = ["File", "Lines", "Tokens/Line"]
        base = Path(args[0]) if args else Path(".")
        table = gen_stats(base)

    if not table:
        print("#### No changes found in core library line counts.")
        return

    table_sorted = sorted(table, key=lambda r: r[1], reverse=True)

    if len(args) == 2:
        print("### Changes:")
        print("```")
        print(tabulate([headers] + table_sorted, headers="firstrow", intfmt=(..., "d", "+d"), floatfmt=(..., ..., ..., ".1f", "+.1f")) + "\n")
        total_delta = sum(r[2] for r in table)
        print(f"\ntotal lines changed: {display_diff(total_delta)}")
        print("```")
    else:
        print(tabulate([headers] + table_sorted, headers="firstrow", floatfmt=".1f") + "\n")
        # Create directory-level summary
        groups = sorted([("/".join(r[0].split("/")[:2]), r[1], r[2]) for r in table_sorted])
        for dir_name, group in itertools.groupby(groups, key=lambda x: x[0]):
            total = sum(item[1] for item in group)
            print(f"{dir_name:30s} : {total:6d}")
        total_lines = sum(r[1] for r in table)
        print(f"\ntotal line count: {total_lines}")
        max_count = int(os.getenv("MAX_LINE_COUNT", "-1"))
        assert max_count == -1 or total_lines <= max_count, f"OVER {max_count} LINES"


#####################################################################################################################################
#                                                               Call                                                                #
#####################################################################################################################################


if __name__ == "__main__":
    main()
