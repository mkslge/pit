"""Module entrypoint for `python -m pit`."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
