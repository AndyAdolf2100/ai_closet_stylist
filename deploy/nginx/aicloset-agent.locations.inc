# For the existing aicloset-agent.wxbjq.top HTTPS server block ONLY.
# Preserve existing listen/server_name/TLS certificates; replace old matching
# locations rather than adding duplicate location / blocks.
# Remove or update more-specific old /app/, /static/, /ops/ or /stylist-api/
# locations that would override this proxy. Do not install as a full server file.
    client_max_body_size 16m;
    # Drain is a local container operation, never an internet endpoint.
    location = /internal { return 404; }
    location ^~ /internal/ { return 404; }

    location / {
        proxy_pass http://127.0.0.1:8465;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # POST SSE: deliver progress immediately, and never replay a failed request.
        proxy_buffering off;
        proxy_cache off;
        proxy_next_upstream off;
        gzip off;
        proxy_connect_timeout 10s;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
