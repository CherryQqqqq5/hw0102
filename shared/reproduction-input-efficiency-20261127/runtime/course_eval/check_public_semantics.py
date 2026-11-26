import sys

if __package__:
    from .public_semantics import main
else:
    from public_semantics import main


if __name__ == "__main__":
    sys.exit(main())
