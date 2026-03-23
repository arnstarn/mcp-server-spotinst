FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

ENV SPOTINST_TOKEN=""
ENV SPOTINST_ACCOUNT_ID=""

EXPOSE 8000

ENTRYPOINT ["mcp-server-spotinst"]
