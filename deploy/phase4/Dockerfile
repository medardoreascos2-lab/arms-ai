FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python tools/verify_phase4_package.py --package-root /app
RUN addgroup --system arms && adduser --system --ingroup arms arms

USER arms

ENTRYPOINT ["python", "tools/verify_phase4_package.py"]
CMD ["--package-root", "/app"]