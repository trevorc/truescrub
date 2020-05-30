FROM python:3.7-alpine AS build

COPY requirements.txt /requirements.txt
WORKDIR /build
RUN apk add --no-cache build-base libzmq zeromq-dev \
 && pip install --install-option='--prefix=/build' -r /requirements.txt \
 && apk del build-base zeromq-dev


FROM python:3.7-alpine
RUN apk add --no-cache libzmq
COPY --from=build /build /usr/local
COPY truescrub /app/truescrub
WORKDIR /app

EXPOSE 9000

CMD ["waitress-serve", "--port", "9000", "truescrub.wsgi:app"]
