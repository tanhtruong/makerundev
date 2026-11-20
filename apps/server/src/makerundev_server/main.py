import uvicorn

from makerundev_server.config import env


def run() -> None:
    uvicorn.run(
        "makerundev_server.app:create_app",
        factory=True,
        host=env("HOST", "127.0.0.1"),
        port=int(env("PORT", "8000")),
    )
