#Databases Project Part 3 - Finstagram

from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

#Initialize the app from Flask
app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

salt = "finsta_salt"

#Configure MySQL
connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)


def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec


#if user's logged in, show personalized homepage
#else, show main page
@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("myindex.html")


#show user's personalized homepage
@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])


#upload photos
@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")


#Feature 1 - View visible photos
#Shows the photoID, photoPoster of each photo visible to the user in reverse chronological order
@app.route("/images", methods=["GET"])
@login_required
def images():
    username = session["username"]
    query = "SELECT photoID, photoPoster FROM Photo WHERE photoID IN (SELECT photoID FROM Photo JOIN Follow ON photoPoster = username_followed WHERE AllFollowers = true AND username_follower = %s AND followStatus = true) OR photoID IN (SELECT photoID FROM SharedWith JOIN BelongTo USING(groupName) WHERE member_username = %s AND groupOwner = owner_username) ORDER BY postingdate DESC"
    with connection.cursor() as cursor:
        cursor.execute(query, (username, username))
    data = cursor.fetchall()
    return render_template("myimages.html", images=data)


#show specific photo
@app.route("/images/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")


#login page
@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")


#registration page
@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")


#login authentication
@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPassword = requestData["password"]
        salted_password = plaintextPassword + salt
        hashedPassword = hashlib.sha256(salted_password.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)


#registration authentication
@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPassword = requestData["password"]
        salted_password = plaintextPassword + salt
        hashedPassword = hashlib.sha256(salted_password.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken" % (username)
            return render_template('myregister.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)


#logout and show main page
@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")


#upload an image
@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        query = "INSERT INTO photo (postingdate, filepath) VALUES (%s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

        
if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug = True)
