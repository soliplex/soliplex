FROM hermes-agent:latest

# Add FastAPI on top of the hermes-agent base image
RUN pip install --no-cache-dir --break-system-packages fastapi

# Copy event server
COPY server.py /opt/hermes/hermes_event_server.py

WORKDIR /opt/hermes

ENV HERMES_HOME=/opt/data
VOLUME ["/opt/data"]

EXPOSE 8642

ENTRYPOINT ["python3", "/opt/hermes/hermes_event_server.py"]
