# Include INSIDE an existing HTTPS server {} after confirming the backend listens on 8466.
# Preserve the /stylist-api/ prefix: proxy_pass must NOT end in a slash.
location ^~ /stylist-api/ {
    client_max_body_size 2m;
    proxy_pass http://127.0.0.1:8466;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_next_upstream off;
    gzip off;
    proxy_connect_timeout 10s;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
}
