#Databases Project Part 4 - Finstagram

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
    return render_template("index.html")


#show user's personalized homepage
@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])


#Features 1, 2 - View visible photos; view further information
@app.route("/images", methods=["GET"])
@login_required
def images():
    username = session["username"]

    with connection.cursor() as cursor:
        #SELECT visible photos and additional information
        query = "SELECT photoID, photoPoster, postingdate, filepath, postingDate, Person.firstName AS posterFirstName, Person.lastName AS posterLastName, TaggedPerson.firstName AS tagFirstName, TaggedPerson.lastName AS tagLastName, TaggedPerson.username AS tagUsername, Likes.username AS likesUsername, rating FROM Photo LEFT OUTER JOIN Person ON photoPoster = username LEFT OUTER JOIN TaggedPerson USING (photoID) LEFT OUTER JOIN Likes USING (photoID) WHERE photoID IN (SELECT photoID FROM Photo JOIN Follow ON photoPoster = username_followed WHERE AllFollowers = TRUE AND username_follower = %s AND followStatus = TRUE) OR photoID IN (SELECT photoID FROM SharedWith JOIN BelongTo USING (groupName) WHERE member_username = %s AND groupOwner = owner_username) OR photoID IN (SELECT photoID FROM Photo WHERE photoPoster = %s) ORDER BY postingdate DESC"
        cursor.execute(query, (username, username, username))
    data = cursor.fetchall()
    
    return render_template("images.html", images = data)


#Feature 3 - Post a photo
#upload an image
@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        username = session["username"]
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        allFollowers = request.form["allFollowers"]

        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)

        with connection.cursor() as cursor:
            #INSERT additional data after uploading a photo
            query = "INSERT INTO Photo (postingdate, filepath, photoPoster, allFollowers) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, username, allFollowers))

        with connection.cursor() as cursor:
            #SELECT most recently added photoID
            query2 = "SELECT photoID FROM Photo WHERE postingDate = (SELECT MAX(postingDate) FROM Photo)"
            cursor.execute(query2)
        photo = cursor.fetchone()

        with connection.cursor() as cursor:
            #SELECT owner_username of the friendgroup the photo is shared with
            query3 = "SELECT DISTINCT owner_username FROM BelongTo WHERE member_username = %s"
            cursor.execute(query3, username)
        data = cursor.fetchall()
        
        #Share the photo with every friendgroup selected in the site form
        query4 = "INSERT INTO SharedWith VALUES (%s, %s, %s)"
        
        for user in data:
            friendgroups = request.form.getlist(user["owner_username"])
            for groupname in friendgroups:
                with connection.cursor() as cursor:
                    cursor.execute(query4, (user["owner_username"], groupname, photo["photoID"]))

        with connection.cursor() as cursor:
            #SELECT data about friendgroups the user belongs to
            query = "SELECT owner_username, groupName FROM BelongTo WHERE member_username = %s"
            cursor.execute(query, username)
        data = cursor.fetchall()          
        
        msg = "Image has been successfully uploaded"
        return render_template("upload.html", friendgroups = data, msg = msg)
    
    msg = "Failed to upload image"
    return render_template("upload.html", msg = msg)


#main upload page
@app.route("/upload", methods=["GET"])
@login_required
def upload():
    username = session["username"]

    with connection.cursor() as cursor:
        #SELECT data about friendgroups the user belongs to
        query = "SELECT owner_username, groupName FROM BelongTo WHERE member_username = %s"
        cursor.execute(query, username)
    data = cursor.fetchall()

    return render_template("upload.html", friendgroups = data)


#Feature 4 - Manage Follows
#main follow page (allows the user to send a follow request; shows list of follow requests the user has received)
@app.route("/followmain", methods=["GET"])
@login_required
def followmain():
    username = session["username"]

    #SELECT follow requester's username, first name, and last name
    query = "SELECT username, firstName, lastName FROM Follow JOIN Person ON username_follower = username WHERE username_followed = %s AND followStatus = 0"
    with connection.cursor() as cursor:
        cursor.execute(query, username)
    data = cursor.fetchall()
    
    return render_template("followmain.html", followreqs = data)


#accept/decline follow requests
@app.route("/managefollows", methods=["POST"])
@login_required
def managefollows():
    username = session["username"]

    if request.form:
        #SELECT follower usernames for outstanding follow requests
        with connection.cursor() as cursor:
            query = "SELECT username_follower FROM Follow WHERE username_followed = %s AND followStatus = 0"
            cursor.execute(query, username)
        data = cursor.fetchall()

        for req in data:
            #handles the case where the user only responded (accepted/declined) to some follow requests
            try:
                status = request.form[req["username_follower"]]
            except:
                #skips the usernames of followers who have an oustanding follow request, which the user didn't accept/decline
                continue
            
            with connection.cursor() as cursor:
                if status == "1":
                    #UPDATE the follow request status
                    query2 = "UPDATE Follow SET followStatus = %s WHERE username_follower = %s AND username_followed = %s"
                    cursor.execute(query2, (status, req["username_follower"], username))
                else:
                    #DELETE the follow request
                    query3 = "DELETE FROM Follow WHERE username_follower = %s AND username_followed = %s"
                    cursor.execute(query3, (req["username_follower"], username))

        #SELECT follow requester's username, first name, and last name
        query = "SELECT username, firstName, lastName FROM Follow JOIN Person ON username_follower = username WHERE username_followed = %s AND followStatus = 0"
        with connection.cursor() as cursor:
            cursor.execute(query, username)
        data = cursor.fetchall()  

        msg = "Follow request list updated"
        return render_template("followmain.html", followreqs = data, msg = msg)
    
    msg = "Something went wrong. Please try again"
    return render_template("followmain.html", msg = msg)


#send a follow request to another user
@app.route("/followuser", methods=["POST"])
@login_required
def followuser():
    username = session["username"]
    
    if request.form:
        followed = request.form["username"]

        with connection.cursor() as cursor:
            #SELECT username of the person the user's trying to follow
            query = "SELECT username FROM Person WHERE username = %s"
            cursor.execute(query, followed)
        data = cursor.fetchone()
        
        if data == None:
            msg = "The username you entered doesn't exist"
            return render_template("followmain.html", msg = msg)
        
        with connection.cursor() as cursor:
            #INSERT the outstanding follow request
            query2 = "INSERT INTO Follow (username_followed, username_follower, followStatus) VALUES (%s, %s, %s)"
            cursor.execute(query2, (followed, username, 0))

        #SELECT follow requester's username, first name, and last name
        query = "SELECT username, firstName, lastName FROM Follow JOIN Person ON username_follower = username WHERE username_followed = %s AND followStatus = 0"
        with connection.cursor() as cursor:
            cursor.execute(query, username)
        data = cursor.fetchall()  

        msg = "Follow request sent"
        return render_template("followmain.html", followreqs = data, msg = msg)
    
    msg = "An unknown error occurred. Please try again"
    return render_template("followmain.html", msg = msg)
    

#Feature 11 - Search by Poster
#show a specific poster's visible photos
@app.route("/posterimages", methods=["POST"])
@login_required
def posterimages():
    username = session["username"]
    
    if request.form:
        poster = request.form["username"]
        
        with connection.cursor() as cursor:
            #SELECT photos and additional data posted by a specific person
            query = "SELECT photoID, photoPoster, postingdate, filepath, postingDate, Person.firstName AS posterFirstName, Person.lastName AS posterLastName, TaggedPerson.firstName AS tagFirstName, TaggedPerson.lastName AS tagLastName, TaggedPerson.username AS tagUsername, Likes.username AS likesUsername, rating FROM Photo LEFT OUTER JOIN Person ON photoPoster = username LEFT OUTER JOIN TaggedPerson USING (photoID) LEFT OUTER JOIN Likes USING (photoID) WHERE (photoID IN (SELECT photoID FROM Photo JOIN Follow ON photoPoster = username_followed WHERE AllFollowers = TRUE AND username_follower = %s AND followStatus = TRUE) OR photoID IN (SELECT photoID FROM SharedWith JOIN BelongTo USING (groupName) WHERE member_username = %s AND groupOwner = owner_username) OR photoID IN (SELECT photoID FROM Photo WHERE photoPoster = %s)) AND photoPoster = %s ORDER BY postingdate DESC"
            cursor.execute(query, (username, username, username, poster))
    data = cursor.fetchall()

    return render_template("images.html", images = data)


#Feature 12 - Add friendgroup
#main friendgroup page (allows the user to create a new friendgroup; shows list of friendgroups the user owns)
@app.route("/friendgroups", methods=["GET"])
@login_required
def friendgroups():
    username = session["username"]
    
    with connection.cursor() as cursor:
        #SELECT friendgroups the user owns
        query = "SELECT * FROM Friendgroup WHERE groupOwner = %s"
        cursor.execute(query, username)
    data = cursor.fetchall()
    
    return render_template("friendgroups.html", friendgroups = data)


#create a new friendgroup
@app.route("/createfriendgroup", methods=["POST"])
@login_required
def createfriendgroup():
    username = session["username"]
    
    if request.form:
        group_name = request.form["group_name"]
        description = request.form["description"]

        with connection.cursor() as cursor:
            #SELECT a matching group name from user's existing friendgroups
            query = "SELECT groupName FROM Friendgroup WHERE groupName = %s AND groupOwner = %s"
            cursor.execute(query, (group_name, username))
        data = cursor.fetchone()
        
        if data != None:
            msg = "A Friendgroup with that name already exists"

            with connection.cursor() as cursor:
                #SELECT friendgroups the user owns
                query = "SELECT * FROM Friendgroup WHERE groupOwner = %s"
                cursor.execute(query, username)
            data = cursor.fetchall()
            
            return render_template("friendgroups.html", friendgroups = data, msg = msg)
        
        with connection.cursor() as cursor:
            #INSERT new friendgroup
            query2 = "INSERT INTO Friendgroup (groupOwner, groupName, description) VALUES (%s, %s, %s)"
            cursor.execute(query2, (username, group_name, description))

        with connection.cursor() as cursor:
            #SELECT friendgroups the user owns
            query = "SELECT * FROM Friendgroup WHERE groupOwner = %s"
            cursor.execute(query, username)
        data = cursor.fetchall()
    
        msg = "Friendgroup successfully made"
        return render_template("friendgroups.html", friendgroups = data, msg = msg)

    msg = "An unexpected error occurred when trying to make a Friendgroup"
    return render_template("friendgroups.html", msg = msg)


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
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)


#logout and show main page
@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

        
if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug = True)
