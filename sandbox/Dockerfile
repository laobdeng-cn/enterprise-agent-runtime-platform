FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=random HOME=/tmp

WORKDIR /workspace

USER 65534:65534

CMD ["python", "-I", "-c", "print('sandbox-ready')"]
