FROM python:3-alpine

ENV PIPENV_VENV_IN_PROJECT=1

COPY app /app
RUN chmod 755 -R /app
WORKDIR /app

RUN apk add --no-cache --virtual .build-deps build-base \
    && pip install --upgrade pip \
    && pip install pipenv \
    && pipenv install --system --deploy \
    && apk del .build-deps

COPY --chmod=555 entrypoint.sh /entrypoint.sh

USER nobody
ENTRYPOINT [ "/entrypoint.sh" ]
