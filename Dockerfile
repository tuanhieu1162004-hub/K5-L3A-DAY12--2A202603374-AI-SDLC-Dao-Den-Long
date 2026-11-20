FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglx-mesa0 libx11-6 libxext6 libxi6 libxrandr2 libxcursor1 libxxf86vm1 libasound2 && rm -rf /var/lib/apt/lists/*
WORKDIR /game
COPY requirements-render.txt .
RUN pip install --no-cache-dir -r requirements-render.txt
COPY game.contract.json .
COPY src ./src
CMD ["python3", "src/panda_game.py"]
