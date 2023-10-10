#!/bin/bash
while [ "1"=="1" ]
do
  python manage.py migrate --run-syncdb
  python manage.py migrate auth
  python manage.py runserver 0.0.0.0:8000 --noreload
  sleep 1
done
