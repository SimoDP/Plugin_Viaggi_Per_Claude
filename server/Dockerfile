FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "mcp>=1.2,<2" "httpx>=0.27"
COPY viaggi_mcp.py .
ENV MCP_TRANSPORT=http PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"
USER nobody
CMD ["python", "viaggi_mcp.py"]
