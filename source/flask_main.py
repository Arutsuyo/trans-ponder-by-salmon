"""
Author: Team Salmon
Flask web app connecting trans*ponder database and website.
The flask web server connects with a mongo database,
where user submitted resources are stored and can be
verified by users with appropriate privileges.
"""

import flask
from flask import request
from flask import url_for

# User Authintication from flask dependancy.
from werkzeug.security import generate_password_hash, check_password_hash

import logging
import sys
import arrow

# Mongo database
from pymongo import MongoClient

import config
CONFIG = config.configuration()

MONGO_CLIENT_URL = "mongodb://{}:{}@{}:{}/{}".format(
    CONFIG.DB_USER,
    CONFIG.DB_USER_PW,
    CONFIG.DB_HOST,
    CONFIG.DB_PORT,
    CONFIG.DB)

if CONFIG.DEBUG is True:
    print("Using URL '{}'".format(MONGO_CLIENT_URL))

app = flask.Flask(__name__)
app.secret_key = CONFIG.SECRET_KEY

####
# Database connection per server process
###
try:
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, str(CONFIG.DB))
    collection = db.memos
except:
    print("Failure opening database. Is Mongo running? Correct password?")
    sys.exit(1)


###
# User Functionality
###

class User:
    def __init__(self, username, password, userType):
        self.username = username
        self.password = password
        self.userType = userType
    
    def save_to_db(self):
        if find_by_username(self.username):
            print("User Already Exists")
            return False
        else:
            print("Creating new user")
            new = {
                "Username" : self.username,
                "password" : self.password,
                "userType" : self.userType,
                }
            collection.insert(new)
            return True
    #end save_to_db
    
def find_by_username(uname):
    for record in collection.find({ "username" : uname}):
        return User(record['username'], record['password'], record['userType'])
    return False
#end find_by_username


@app.route('/_register')
def register_user():
    app.logger.debug("Checking Registration")
    username = request.args.get('username', type=str)
    password = request.args.get('password', type=str)
    userType = request.args.get('userType', type=str)

    if User(username, generate_password_hash(password), userType).save_to_db():
        app.logger.debug("Registration Successful")
        result = {'error' : False, 'message': 'User registered successfully'}
        return flask.jsonify(result=result)
    else:
        app.logger.debug("Failed Registration")
        result = {'error': "User failed"}
        return flask.jsonify(result = result)
    

@app.route('/_login')
def login_user():
    app.logger.debug("Checking Login")
    username = request.args.get('username', type=str)
    password = request.args.get('password', type=str)
    userType = request.args.get('userType', type=str)
    
    user = find_by_username(username)
    
    if user and check_password_hash(user.password, password):
        app.logger.debug("Correct Login")
        result = {'message': 'Password is correct'}
        return flask.jsonify(result = result)  # You'll want to return a token that verifies the user in the future
    app.logger.debug("Failed Login")
    result = {'error': 'User or password are incorrect'}
    return flask.jsonify(result = result)

###
# End User Functionality
###



###
# Pages
###
@app.route("/")
@app.route("/index")
def index():
    app.logger.debug("Main page entry")
    return flask.render_template('index.html')


# A function to display memos on page load
@app.route("/_disp")
def disp():
    app.logger.debug("Initializing memos.")
    result = {"memos": get_memos()}
    return flask.jsonify(result=result)


# Create a new memo
@app.route("/_create")
def create():
    app.logger.debug("Creating memo")
    # Get the memo contents from javascript side.
    contents = request.args.get('contents')
    date = request.args.get('date')
    # Find a new index for the next memo:
    cur_index = memo_idx()
    try:
        # Try block is for checking if date is valid.
        valid = arrow.get(date, 'YYYY-M-D')
    except:
        er = "Not a good time"
        app.logger.debug(er)
        result = {"error": er}
        return flask.jsonify(result=result)

    new = {"type": "dated_memo",
           "date": date,
           "text": contents,
           "index": cur_index}
    collection.insert(new)
    result = {"memos": get_memos()}
    return flask.jsonify(result=result)


# Delete a memo
@app.route("/_del")
def delete():
    # Get the index for the memo to delete from js:
    id = request.args.get('id', type=int)
    app.logger.debug("Deleting memo")
    # Delete the memo:
    del_memo(id)
    # Send the remaining memos over to js:
    result = {"memos": get_memos()}
    return flask.jsonify(result=result)


@app.errorhandler(404)
def page_not_found(error):
    app.logger.debug("Page not found")
    return flask.render_template('page_not_found.html',
                                 badurl=request.base_url,
                                 linkback=url_for("index")), 404


##############
# Functions available to the page code above
##############
def humanize_arrow_date(date):
    """
    Date is internal UTC ISO format string.
    Output should be "today", "yesterday", "in 5 days", etc.
    Arrow will try to humanize down to the minute, so we
    need to catch 'today' as a special case.
    """
    try:
        then = arrow.get(date, 'YYYY-M-D').to('local')
        # If we are in a tz less than Greenwhich (West), then the memos are getting a date
        # that is one day too soon, so shift forward a day if we are in such a time zone.
        # the [-6]th element of the arrow time string is the sign on the timezone segment of the time.
        # Thus, if it is "-", we need to shift forward one day.
        East_of_Greenwhich = arrow.now().isoformat()[-6]
        if East_of_Greenwhich == "-":
            then = then.shift(days=+1)
        now = arrow.utcnow().to('local')

        # Some special cases for the humanize functions: today, tomorrow, yesterday.
        if then.date() == now.date():
            human = "Today"
        elif str(then.date() - now.date()) == "1 day, 0:00:00":
            human = "Tomorrow"
        elif str(now.date() - then.date()) == "1 day, 0:00:00":
            human = "Yesterday"
        else:
            human = then.humanize()
    except:
        human = date
    return human


def get_memos():
    """
    Returns all memos in the database, in a form that
    can be inserted directly in the 'session' object,
    and in sorted order.
    """
    records = []
    for record in collection.find({"type": "dated_memo"}):
        record['a_date'] = arrow.get(record['date'], 'YYYY-M-D').isoformat()
        del record['_id']
        record['disp_date'] = humanize_arrow_date(record.get('date'))
        records.append(record)
    # Sort the records by arrow date:
    records.sort(key=lambda i: arrow.get(i['a_date']))
    return records


def memo_idx():
    # The easiest way to delete memos is if each has
    # an index that is unique for each memo.
    # This might be slow for a very large database?
    new_index = 0
    for record in collection.find():
        if record["index"] > new_index:
            new_index = record["index"]
    new_index += 1
    return new_index


def del_memo(idx):
    """
    Deletes a memo with a specified index from the database.
    """
    for record in collection.find({"index": idx}):
        collection.delete_one(record)

###
# Test Pages
###

@app.route("/testUser")
def testPage():
    app.logger.debug("Test page entry")
    return flask.render_template('testUser.html')


if __name__ == "__main__":
    app.debug = CONFIG.DEBUG
    app.logger.setLevel(logging.DEBUG)
    app.run(port=CONFIG.PORT, host="localhost")
    
