# base image
FROM python:latest

# create code directory
RUN mkdir -p /usr/src/discord_bot
WORKDIR /usr/src/discord_bot

# copy current dir into docker dir
COPY . .

# install requirements from file
RUN pip install -r requirements.txt

# run discord bot
CMD ["python", "main.py"]