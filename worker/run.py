from __future__ import annotations

import argparse
import time
import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', default='http://127.0.0.1:8015')
    parser.add_argument('--interval', type=float, default=2.0)
    args = parser.parse_args()

    while True:
        try:
            r = httpx.get(f"{args.backend}/api/worker/jobs/next", timeout=10)
            r.raise_for_status()
            job = r.json().get('job')
            if job:
                httpx.post(f"{args.backend}/api/worker/jobs/{job['id']}/complete", timeout=20)
            time.sleep(args.interval)
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
