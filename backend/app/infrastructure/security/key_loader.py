from pathlib import Path


class JWTKeyConfigurationError(RuntimeError):
    pass


def load_pem(path: Path | None, label: str) -> str:
    if path is None:
        raise JWTKeyConfigurationError(f"{label} path is not configured")

    try:
        data = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise JWTKeyConfigurationError(f"{label} could not be loaded") from exc

    if "BEGIN" not in data or "KEY" not in data:
        raise JWTKeyConfigurationError(f"{label} is not valid PEM text")

    return data
