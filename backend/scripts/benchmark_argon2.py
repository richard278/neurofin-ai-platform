import argparse
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path

from app.core.config import Settings
from app.infrastructure.security.argon2_password_hasher import Argon2idPasswordHasher


def nearest_rank_percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = math.ceil(percentile * len(ordered))
    return ordered[rank - 1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.samples < 5:
        raise ValueError("samples must be >= 5")

    settings = Settings(_env_file=None)
    hasher = Argon2idPasswordHasher(settings)
    password = "neurofin-argon2-benchmark-input"
    encoded = hasher.hash(password)

    timings_ms: list[float] = []
    for _ in range(args.samples):
        started = time.perf_counter()
        verified = hasher.verify(password, encoded)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if not verified:
            raise RuntimeError("benchmark verification failed")
        timings_ms.append(elapsed_ms)

    median_verify_ms = round(statistics.median(timings_ms), 3)
    p95_verify_ms = round(nearest_rank_percentile(timings_ms, 0.95), 3)

    justification = (
        f"Candidate Argon2id configuration (memory_cost={settings.argon2_memory_cost_kib} KiB [64 MiB], "
        f"time_cost={settings.argon2_time_cost}, parallelism={settings.argon2_parallelism}) "
        f"measured median={median_verify_ms}ms and p95={p95_verify_ms}ms over {args.samples} samples. "
        "The 64 MiB memory cost provides memory-hardness defense against GPU/ASIC cracking. "
        "This latency evidence is specific to the current execution environment and is NOT claimed "
        "to be a universally optimal baseline configuration. Independent benchmarking on target "
        "deployment hardware is required prior to production deployment."
    )

    evidence = {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "algorithm": "Argon2id",
        "memory_cost_kib": settings.argon2_memory_cost_kib,
        "time_cost": settings.argon2_time_cost,
        "parallelism": settings.argon2_parallelism,
        "hash_len": settings.argon2_hash_len,
        "salt_len": settings.argon2_salt_len,
        "samples": args.samples,
        "median_verify_ms": median_verify_ms,
        "p95_verify_ms": p95_verify_ms,
        "percentile_method": "nearest-rank: ceil(percentile * samples), 1-indexed",
        "selection_justification": justification,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
