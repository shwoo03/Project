FROM php:8.2-apache
COPY src/ /var/www/html/
COPY flag.txt /flag.txt
RUN mkdir -p /var/www/html/data/posts \
 && chown -R www-data:www-data /var/www/html /flag.txt
