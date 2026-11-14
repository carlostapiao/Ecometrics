FROM python@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home appuser \
    && mkdir -p /data/evidencias /var/lib/ecometrics/staticfiles \
    && chown -R appuser:appuser /data/evidencias /var/lib/ecometrics
COPY --chown=appuser:appuser src/ .
RUN DJANGO_SECRET_KEY=build-collectstatic-only-not-for-runtime python manage.py collectstatic --noinput \
    && chown -R appuser:appuser /var/lib/ecometrics/staticfiles
USER appuser
EXPOSE 8000
CMD ["gunicorn", "configuracion.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
