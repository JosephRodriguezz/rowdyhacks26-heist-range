# Standalone Red prototype (red/) - zero third-party dependencies, standard library only.
# This packages ONLY the Red prototype and its tests so it can run identically on any
# machine, not just the one it was built on. It does not package blue-team/, backend/,
# frontend/, or anything else in the repo.
FROM python:3.12-slim

WORKDIR /app

COPY red/ ./red/
COPY tests/ ./tests/

# Fail the build itself if the package doesn't even compile, instead of discovering that
# on whatever machine someone tries to run this on.
RUN python -m compileall -q red

# Default: list available scenarios. Override with any `red.prototype.cli` subcommand, e.g.:
#   docker run --rm red-prototype run --scenario availability --mode deterministic_baseline
#   docker run --rm red-prototype evaluate
#   docker run --rm --entrypoint python red-prototype -m unittest discover -s tests -v
ENTRYPOINT ["python", "-m", "red.prototype.cli"]
CMD ["scenarios"]
