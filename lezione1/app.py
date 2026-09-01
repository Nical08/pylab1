from flask import Flask
from flask import render_template
import re
from flask import abort

app = Flask(__name__)

@app.route('/')
def home():
    return "hi"

@app.route('/about')
def about():
    return "abaut you "

@app.route("/ciao/<nomee>")
def nome(nomee):
    return ("ciao " + nomee)

@app.route("/hello/<string:inputname>")
def saluto (inputname = ''):
    pattern = re.compile(r"[0-9]+")
    matches = pattern.findall(inputname)
    if matches and len(matches)>0:
        abort(400, description="Name must not contain number")


    return render_template('hello.html', name=inputname)
    

        
    
        
   

if __name__ == "__main__":
    app.run(debug=True)
