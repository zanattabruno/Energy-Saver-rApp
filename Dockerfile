FROM leoliveroso/cplex-ubuntu-python36:1.0

RUN apt update && apt upgrade -y && apt autoremove -y

WORKDIR /app

COPY src/. .

COPY requirements.txt .

RUN /usr/local/bin/python3.6 -m pip install --upgrade pip && /usr/local/bin/python3.6 -m pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["sleep","315360000"]
