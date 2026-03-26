FROM nginx:1.25-alpine
COPY nginx.conf.template /etc/nginx/nginx.conf.template
EXPOSE 8080
CMD ["/bin/sh", "-c", "envsubst '${USER_SERVICE_HOST} ${POST_SERVICE_HOST} ${COMMENT_SERVICE_HOST} ${NOTIFICATION_SERVICE_HOST}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]
