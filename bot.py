
from flask import Flask
from threading import Thread

app = Flask('')


@app.route('/')
def home():
  chno = "Bot is running!"
  return chno


def run():
  app.run(host='0.0.0.0', port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# Make sure keep_alive() is called right before your bot runs
keep_alive()
