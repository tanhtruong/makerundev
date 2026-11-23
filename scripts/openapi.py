import json
import tempfile
from pathlib import Path

from makerundev_server import create_app

SCHEMA = Path(__file__).resolve().parent.parent / "apps" / "server" / "openapi.json"


def render() -> str:
    with tempfile.TemporaryDirectory() as data_dir:
        schema = create_app(data_dir=Path(data_dir)).openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    SCHEMA.write_text(render())


if __name__ == "__main__":
    main()
