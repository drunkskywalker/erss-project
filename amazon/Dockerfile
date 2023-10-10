FROM python:3
ENV PYTHONUNBUFFERED 1

RUN apt update && apt-get -y --no-install-recommends install build-essential\
 libboost-all-dev
RUN mkdir /code
WORKDIR /code
ADD requirements.txt /code/
RUN pip install --upgrade pip
RUN pip install --upgrade wheel
RUN pip install --upgrade setuptools
RUN pip install --upgrade requests
RUN pip install -r requirements.txt
ADD . /code/

CMD ["bash", "run.sh"]
