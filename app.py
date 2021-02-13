from flask import Flask, flash, jsonify, redirect, render_template, request, session
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from tempfile import mkdtemp
from flask_session import Session
import sqlite3
import csv
import pandas as pd
import json
import requests

app = Flask(__name__)
app.secret_key = "super secret key"
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = mkdtemp()

#configuring flask
conn = sqlite3.connect('fixtures.db', check_same_thread=False)
db = conn.cursor()
#making connection to database, can now use db for db.execute
def update(): #defining an update function which downlaods a CSV from the web containing fixtures and results, can be scheduled or called each time page is opened
    url=("https://fixturedownload.com/download/epl-2020-GMTStandardTime.csv")
    with requests.Session() as s:
        download = s.get(url)
        decoded_content = download.content.decode('utf-8')
        reader = csv.reader(decoded_content.splitlines(), delimiter=',') #19-21 downloads file, converts from unicode to plain text and adds in spaces
        next(reader, None) #removes header row
        db.execute('DELETE FROM fixturelist;',); #when fixtures are updated, old ones are deleted to avoid duplicates
        for row in reader: #loop accross csv
            db.execute("INSERT INTO fixturelist (roundnum, date, location, home, away, result) VALUES(?, ?, ?, ?, ?, ?)", (row[0], row[1], row[2], row[3], row[4], row[5])) #write values into db table
sched = BackgroundScheduler(daemon=True)
sched.add_job(update,'interval',minutes=60)
sched.start() #26-28 used apscheduler module to call update function every hour

@app.route("/")
def index():
    return render_template("index.html") #index located at '/' renders the homepage template 'index.html'

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        if request.form.get("username") == "" or request.form.get("password") == "":
            return render_template("login.html", error=True, message = "Both fields must be completed - please try again.")
        # Query database for username
        rows = (db.execute("SELECT * FROM users WHERE username = :username", {"username": request.form.get("username")})).fetchall()
        print(rows)
        if rows == []:
            return render_template("login.html", error=True, message = "No user with that name was found - please try again or register.")
        if not check_password_hash(rows[0][2], request.form.get("password")):
            return render_template("login.html", error=True, message = "Incorrect password - please try again or register.")
        session['logged_in'] = True
        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        conn = sqlite3.connect('fixtures.db')
        c = conn.cursor()
        if request.form.get("password") != request.form.get("confirmPassword"):
            return render_template("register.html", error = True, message = "Passwords did not match - please try again.")
        if request.form.get("username") == "" or request.form.get("password") == "":
            return render_template("register.html", error = True, message = "You must complete all fields - please try again.")
        if len(request.form.get("password")) < 6:
            return render_template("register.html", error = True, message = "Passowrd must be 6 characters or longer - please try again.")
        username = request.form.get("username")
        rows = (c.execute("SELECT username FROM users WHERE username = :i", {"i": username})).fetchone()
        if rows != None:
            return render_template("register.html", error = True, message = "That username is already taken - please try again.")
        hashedPassword = generate_password_hash(request.form.get("password"), "sha256")
        c.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, hashedPassword))
        conn.commit()
        return render_template("login.html", error=True, message = "Account created successfully! Please login below:")
    else:
        return render_template("register.html", error=False)

@app.route("/fixtures", methods=["GET", "POST"])
def fixtures():
    if request.method == "POST": #if request is a POST, user has input a gameweek to view using form, in this case week variable gets desired value
        week=request.form.get("gw")
        rows = db.execute("SELECT roundnum, date, home, away, result FROM fixturelist WHERE roundnum = :i", {"i": week})
        return render_template("fixtures.html", rows=rows)
    else: #else request must be a GET so by default table shows the next gameweek
        nums=[]
        now = datetime.date(datetime.now())
        dates = db.execute("SELECT roundnum, date FROM fixturelist") #creating a list which corresponds dates and gameweeks/round nums
        for date in dates:
            string = date[1][0: 10]
            new=string[8:10] + '-' + string[3:5] + '-' + string[0:2]
            dt=datetime.date(datetime.strptime(new, '%y-%m-%d')) #CSV gives date in non pythonic format - 45-47 uses string comprehension to give correct format for comparison with current datetime from datetime module
            if dt >= now:
                nums.append(date[0]) #creates a list of all the roundnums in the future (date>= now)
        week=min(nums) #selects smallest value in the future (next gameweek)
        rows = db.execute("SELECT roundnum, date, home, away, result FROM fixturelist WHERE roundnum = :i", {"i": week}) #creates a list with appropriate values from db
        return render_template("fixtures.html", rows=rows) #renders the fixtures template and provides the list containing the data needed to create fixture tables

@app.route("/news")
def news():
    return render_template("news.html") #simple section of the site displaying a news page by rendering the news.html template

@app.route("/members")
def member():
    if not session.get('logged_in'):
        return render_template('login.html', error = True, message = 'Members only zone, please log in:')
    else:
        return render_template("members.html")

@app.route("/tips")
def tips():
    return render_template("tips.html")