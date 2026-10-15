FROM python:3.12-slim

WORKDIR /app
COPY . .

# The CLI and MCP server need nothing. Only the console does.
RUN pip install --no-cache-dir "gradio>=6"

EXPOSE 7860
ENV PORT=7860

HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','7860')+'/')"

CMD ["python", "app.py"]
