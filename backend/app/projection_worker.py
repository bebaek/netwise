import argparse
import logging
import signal
import threading
import time
from datetime import timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.projection_jobs import (
    claim_projection_job,
    delete_expired_projection_jobs,
    execute_projection_job,
    recover_stale_projection_jobs,
)

logger = logging.getLogger(__name__)


def run_worker(*, once: bool = False) -> None:
    settings = get_settings()
    stop = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    def maintain_jobs() -> None:
        try:
            with SessionLocal() as db:
                deleted = delete_expired_projection_jobs(db)
                recovered = recover_stale_projection_jobs(
                    db,
                    older_than=timedelta(hours=settings.projection_worker_stale_hours),
                )
        except SQLAlchemyError:
            logger.warning("Projection job maintenance is waiting for the database", exc_info=True)
            return
        if deleted:
            logger.info("Deleted %s expired projection job(s)", deleted)
        if recovered:
            logger.warning("Recovered %s stale projection job(s)", recovered)

    maintain_jobs()
    next_maintenance = time.monotonic() + 3600

    while not stop.is_set():
        if time.monotonic() >= next_maintenance:
            maintain_jobs()
            next_maintenance = time.monotonic() + 3600
        try:
            with SessionLocal() as db:
                job = claim_projection_job(db)
            if job is not None:
                logger.info("Running projection job %s", job.id)
                execute_projection_job(SessionLocal, job.id)
                logger.info("Finished projection job %s", job.id)
            elif once:
                return
            else:
                stop.wait(settings.projection_worker_poll_seconds)
        except SQLAlchemyError:
            logger.warning("Projection worker is waiting for the database", exc_info=True)
            stop.wait(settings.projection_worker_poll_seconds)
        if once:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run queued Netwise projection jobs")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
