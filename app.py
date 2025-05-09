from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return 'Hola, Flask está funcionando!'

app.run()
