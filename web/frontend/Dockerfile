FROM nginx:1.27-alpine

# O modelo vira /etc/nginx/conf.d/default.conf na subida (substituindo ${HTTPS_PORT})
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY snippets/ /etc/nginx/snippets/
COPY public/ /usr/share/nginx/html/

# Certificados (gerados por scripts/gerar-certificado.sh) são montados em /etc/nginx/certs
EXPOSE 80 443
