FROM python:3-alpine

ENV PIPENV_VENV_IN_PROJECT=1

COPY app /app
RUN chmod 755 -R /app
WORKDIR /app

RUN pip install --upgrade pip && pip install pipenv
RUN pipenv install --system --deploy

COPY --chmod=555 entrypoint.sh /entrypoint.sh

USER nobody
ENTRYPOINT [ "/entrypoint.sh" ]