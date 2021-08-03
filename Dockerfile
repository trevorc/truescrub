FROM python:3.7-alpine AS build

COPY requirements.txt /requirements.txt
WORKDIR /build
RUN pip install --install-option='--prefix=/build' -r /requirements.txt


FROM python:3.7-alpine
COPY --from=build /build /usr/local
COPY truescrub /app/truescrub
WORKDIR /app

EXPOSE 9000

CMD ["waitress-serve", "--port", "9000", "truescrub.wsgi:app"]
