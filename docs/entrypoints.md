# Entrypoints And Package Metadata

This document covers the small files that start the CLI or expose package-level
metadata.

## `src/pit/__init__.py`

Purpose:

- Marks `src/pit` as a Python package.
- Defines package-level metadata.

### `__version__`

Current package version string:

```python
__version__ = "0.1.0"
```

Used by:

- `src/pit/cli.py`, where `pit --version` prints `pit <version>`.

There are no functions in this file.

## `src/pit/__main__.py`

Purpose:

- Allows the package to be run as a module with `python -m pit` when `src` is on
  `PYTHONPATH` or the package is installed.

Behavior:

```python
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

There are no defined functions in this file. It imports `main()` from
`src/pit/cli.py` and calls it only when the module is executed as a script.

## Repo-Root `pit`

Purpose:

- Development checkout entrypoint.
- Lets contributors run `./pit ...` without installing the package.

Behavior:

1. Resolves the repository root from the script path.
2. Prepends `<repo>/src` to `sys.path`.
3. Imports `main()` from `pit.cli`.
4. Calls `main()` when executed as a script.

There are no defined functions in this script. Its main implementation detail is
the `sys.path` insertion, which makes the local source tree importable before
dispatching to the real CLI.
