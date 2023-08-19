FROM python:3.9

WORKDIR /clothion
COPY . .

RUN pip install -e .

CMD ["clothion"]
