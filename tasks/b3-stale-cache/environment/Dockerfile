FROM zenml-bench/base:0.96.4
WORKDIR /app/nightly
COPY nightly/run.py nightly/data/ ./
RUN mkdir -p data && mv train.csv data/train.csv && zenml init
