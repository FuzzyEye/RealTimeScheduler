import sys
from src.app.cli import build_parser
from src.app.runner import run_app


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run_app(args))
