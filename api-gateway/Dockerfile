FROM nginx:1.25-alpine
COPY nginx.conf.template /etc/nginx/nginx.conf.template
EXPOSE 8080
CMD ["/bin/sh", "-c", "export DNS_RESOLVER=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf) && envsubst '${USER_SERVICE_HOST} ${POST_SERVICE_HOST} ${COMMENT_SERVICE_HOST} ${NOTIFICATION_SERVICE_HOST} ${DNS_RESOLVER}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]
