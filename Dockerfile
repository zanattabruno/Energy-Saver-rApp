FROM zanattabruno/cplex-python38:latest

RUN apt update && apt upgrade -y && apt autoremove -y

WORKDIR /app

COPY src/rApp_catalogue_client.py src/rApp_Energy_Saver.py src/Solution_Tools.py src/Solution_Tools.py src/UE_Consumer.py src/UE_Generator.py /app/

COPY src/optimal_model/. /app/optimal_model/

COPY requirements.txt .

RUN /usr/local/bin/python3.8 -m pip install --upgrade pip && /usr/local/bin/python3.8 -m pip install -r requirements.txt

ENTRYPOINT ["sleep","999999999"]
