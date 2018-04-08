"""
Author: Team Salmon: Sam Champer, Nara Emery, Andrea Nosler
Flask web app connecting trans*ponder database and website.
The flask web server connects with a mongo database,
where user submitted resources are stored and can be
verified by users with appropriate privileges.
"""

import sys
import logging
import flask  # Web server tool.
from werkzeug.security import generate_password_hash, check_password_hash  # User authentication.
from pymongo import MongoClient  # Mongo database
import config  # Get config settings from credentials file

####
# App globals:
###
CONFIG = config.configuration()

MONGO_CLIENT_URL = "mongodb://{}:{}@{}:{}/{}".format(
    CONFIG.DB_USER,
    CONFIG.DB_USER_PW,
    CONFIG.DB_HOST,
    CONFIG.DB_PORT,
    CONFIG.DB)

if CONFIG.DEBUG is True:
    print("Using URL '{}'".format(MONGO_CLIENT_URL))

password_for_volunteers = CONFIG.PASSWORD_FOR_VOLUNTEERS

app = flask.Flask(__name__)
app.secret_key = CONFIG.SECRET_KEY


####
# Database connection per server process:
###
try:
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, str(CONFIG.DB))
    collection = db.resources
    users_collection = db.users
except:
    print("Failure opening database. Is Mongo running? Correct password?")
    sys.exit(1)


###
# User account functionality:
###
class User:
    def __init__(self, username, password, userType):
        self.username = username
        self.password = password # Never storing the actual password, just a hash
        self.userType = userType

    # ***ONLY EVER CALL WHEN CHAINED AND USING generate_password_hash(pword) ***
    # such as: User(username, generate_password_hash(password), userType).save_to_db()
    # This means no passwords are ever saved in the database, only the hashs of the passwords
    def save_to_db(self):
        app.logger.debug("Checking if user exists")
        if find_by_username(self.username):
            app.logger.debug("User Already Exists")
            return False
        else:
            app.logger.debug("Creating new user")
            new = {
                "username": self.username,
                "password": self.password,
                "userType": self.userType,
            }
            res = users_collection.insert(new)
            if hasattr(res, "writeConcernError"):
                app.logger.debug(res["writeConcernError"])
                return False
            elif hasattr(res, "writeError"):
                app.logger.debug(res["writeError"])
                return False
            else:
                app.logger.debug("Created")
                return True
                # end save_to_db


# Find user by username, if it exists, return the record, if it doesn't, return False
def find_by_username(uname):
    app.logger.debug("Finding User: " + uname)
    for record in users_collection.find({"username": uname}):
        app.logger.debug(record['username'], record['userType'])
        return User(record['username'], record['password'], record['userType'])
    return False
# end find_by_username


@app.route('/_register')
def register_user():
    app.logger.debug("Checking Registration")
    # Get User information
    username = flask.request.args.get('username', type=str)
    password = flask.request.args.get('password', type=str)

    if username == '' or password == '':
        result = {'error' : 'Username or password was blank'}
        return flask.jsonify(result=result)

    if flask.request.args.get('volunteer_pass', type=str) == password_for_volunteers:
        userType = "volunteer"
    else:
        userType = "standard user"

    # Try and register user
    if User(username, generate_password_hash(password), userType).save_to_db():
        app.logger.debug("Registration Successful")
        result = {'message': 'User registered successfully as ' + userType}
        return flask.jsonify(result=result)
    else:
        # If failed, See errors possible in save_to_db()
        app.logger.debug("Failed Registration")
        result = {'error': "User failed"}
        return flask.jsonify(result=result)

@app.route('/_checkname')
def check_user_name():
    app.logger.debug("Checking Name Availability")
    # Get User information
    username = flask.request.args.get('username', type=str)

    if find_by_username(username):
        app.logger.debug("User Exists")
        return flask.jsonify(result=True)
    else:
        app.logger.debug("User does not exist")
        return flask.jsonify(result=False)



@app.route('/_login')
def login_user():
    app.logger.debug("Checking Login")
    username = flask.request.args.get('username', type=str)
    password = flask.request.args.get('password', type=str)

    # See if user exists
    user = find_by_username(username)
    if user:
        # Make sure hashes match the password (no passwords are ever saved)
        if check_password_hash(user.password, password):
            app.logger.debug("Correct Login")
            if user.userType == "volunteer":
                # This is a volunteer user, note that in the session
                # variable so user has access to unverified resources.
                flask.session["volunteer"] = True
            else:
                flask.session["volunteer"] = False
            result = {'message': 'Password is correct'}
            return flask.jsonify(result=result)  # You'll want to return a token that verifies the user in the future
        else:
            # Hashes didn't match
            app.logger.debug("Password failed")
            result = {"error": "password failed", "message": "login failed"}
            return flask.jsonify(result=result)
    else:
        # User didn't exist
        app.logger.debug("No User Exists")
        result = {"error": "username failed", "message": "login failed"}
        return flask.jsonify(result=result)
###
# End User Functionality
###


###
# Pages
###
# Main index page
@app.route("/")
@app.route("/index")
def index():
    flask.session["volunteer"] = False
    app.logger.debug("Main page entry")
    return flask.render_template('index.html')


# Route to log in to the page.
@app.route("/register")
def register():
    app.logger.debug("registration Page")
    return flask.render_template('registration.html')


# Route to submit a new resource.
@app.route("/submit")
def submit():
    app.logger.debug("Submission Page")
    return flask.render_template('submit.html')


# A function to display resources to the front end from the db.
@app.route("/_disp")
def disp():
    resource_type = flask.request.args.get('res_type')
    filter_ohp = False
    if flask.request.args.get('filter_ohp') == "True":
        filter_ohp = True
    filter_monitor_hormones = False
    if flask.request.args.get('filter_monitor_hormones') == "True":
        filter_monitor_hormones = True
    filter_pvt_ins = False
    if flask.request.args.get('filter_pvt_ins') == "True":
        filter_pvt_ins = True
    if resource_type:
        app.logger.debug("Pulling resources of type: " + resource_type)
        result = {"resources": get_db_entries(resource_type, filter_ohp, filter_monitor_hormones, filter_pvt_ins)}
        return flask.jsonify(result=result)
    else:
        return flask.jsonify(dict())

# Function to add a new resource to the db:
@app.route("/_create")
def create():
    app.logger.debug("Uploading new resource to db.")
    # Get resource contents from user.
    type = flask.request.args.get('type')
    name = flask.request.args.get('name')
    office_name = flask.request.args.get('office_name')
    address = flask.request.args.get('address')
    phone = flask.request.args.get('phone')
    email = flask.request.args.get('email')
    website = flask.request.args.get('website')
    takes_ohp = interp_bool(flask.request.args.get('takes_OHP'))
    takes_private_ins = interp_bool(flask.request.args.get('takes_private_ins'))
    sliding_scale = interp_bool(flask.request.args.get('sliding_scale'))
    diversity_aware = interp_bool(flask.request.args.get('diversity_aware'))
    paperwork_not_only_mf = interp_bool(flask.request.args.get('paperwork_not_only_mf'))
    paperwork_asks_for_pronoun = interp_bool(flask.request.args.get('paperwork_asks_for_pronoun'))
    can_monitor_hormones = interp_bool(flask.request.args.get('can_monitor_hormones'))
    notes = flask.request.args.get('notes')
    # Add a new entry to the database with the contents submitted by the user.
    new = {
        "type": type,
        "name": name,
        "office_name": office_name,
        "address": address,
        "phone": phone,
        "email": email,
        "website": website,
        "takes_OHP": takes_ohp,
        "takes_private_ins": takes_private_ins,
        "sliding_scale": sliding_scale,
        "diversity_aware": diversity_aware,
        "paperwork_not_only_mf": paperwork_not_only_mf,
        "paperwork_asks_for_pronoun": paperwork_asks_for_pronoun,
        "can_monitor_hormones": can_monitor_hormones,
        "notes": notes,
        "verified": False
        }

    if does_resource_exist(type, name):
        result = {"error" : "Resource is already in the database"}
    else:
        res = collection.insert(new)
        if hasattr(res, "writeConcernError"):
            app.logger.debug(res["writeConcernError"])
            result = {"error" : res["writeConcernError"]}
        elif hasattr(res, "writeError"):
            app.logger.debug(res["writeError"])
            result = {"error" : res["writeError"]}
        else:
            app.logger.debug("Resource Created")
            result = {"message" : "Resource created successfully"}
            
    return flask.jsonify(result=result)


# Delete a resource
@app.route("/_del")
def delete():
    if not flask.session["volunteer"]:
        # Only volunteers have access to this function.
        return flask.jsonify(result={"err": "err"})
    # Get the name of the resource to delete from user:
    res_name = flask.request.args.get('res_name')
    app.logger.debug("Deleting resource")
    del_resource(res_name)

    # Return to the remaining unverified resources:
    result = {"resources": get_unverified()}
    return flask.jsonify(result=result)


# Get unverified resources.
@app.route("/_unverified")
def unverified():
    # Only accessible to volunteers users
    # such that they can go through unverified
    # resources and mark them verified or delete
    # them as appropriate.
    if not flask.session["volunteer"]:
        return flask.jsonify(result={"err": "err"})
    result = {"resources": get_unverified()}
    return flask.jsonify(result=result)


# verify a resource
@app.route("/_verify")
def verify():
    if not flask.session["volunteer"]:
        # Only volunteers have access to this function.
        return flask.jsonify(result={err: "err"})
    # Get the name of the resource to verify from user input:
    res_name = flask.request.args.get('res_name')
    app.logger.debug("verifying resource")
    verify_resource(res_name)
    # Return to the remaining unverified resources:
    result = {"resources": get_unverified()}
    return flask.jsonify(result=result)


@app.route("/_allcategories")
def scrap_all_resource_list():
    """
    Scraps the collection to generate a list of all resource categories
    """
    all_types = collection.distinct( "type" )
    result = {"types" : all_types}
    print(result)
    return flask.jsonify(result=result)

@app.route("/_verifiedcategories")
def scrap_verified_resource_list():
    """
    Scraps the collection to generate a list of verified categories
    """
    all_types = collection.distinct( "type", { "verified" : True } )
    result = {"types" : all_types}
    print(result)
    return flask.jsonify(result=result)

@app.route("/_unverifiedcategories")
def scrap_unverified_resource_list():
    """
    Scraps the collection to generate a list of unverified categories
    """
    all_types = collection.distinct( "type", { "verified" : False } )
    result = {"types" : all_types}
    print(result)
    return flask.jsonify(result=result)


# Error page(s)
@app.errorhandler(404)
def page_not_found(error):
    app.logger.debug("Page not found")
    return flask.render_template('page_not_found.html',
                                 badurl=flask.request.base_url,
                                 linkback=flask.url_for("index")), 404


##############
# Functions available to the page code above
##############

def does_resource_exist(type, name):
    """
    Scraps the collection to see if the resource exists already
    """
    app.logger.debug("Finding resource: ", type, ", ", name)
    for record in collection.find({"type": type, "name" : name}):
        app.logger.debug(record)
        return True
    return False

def get_db_entries(resource_type, filter_ohp, filter_monitor_hormones, filter_pvt_ins):
    """
    Returns all matching resources, in a form that
    can be inserted directly in the 'session' object,
    in sorted order.
    Can have three specified filter criteria,
    which default to turned off.
    """
    records = []
    for record in collection.find({"type": resource_type}):
        matching_record = True
        del record['_id']
        if record["verified"] is False:
            matching_record = False
        # if filter_ohp and (not record["takes_OHP"] or record["takes_OHP"] != "Yes"):
        # if filter_monitor_hormones and (not record["can_monitor_hormones"] or record["can_monitor_hormones"] != "HRT" ):
        # if filter_pvt_ins and (not record["takes_private_ins"] or record["takes_private_ins"] != "Yes"):
        if filter_ohp and not record["takes_OHP"]:
            matching_record = False
        if filter_monitor_hormones and not record["can_monitor_hormones"]:
            matching_record = False
        if filter_pvt_ins and not record["takes_private_ins"]:
            matching_record = False
        if matching_record:
            records.append(record)
    # Sort the records by name:
    records.sort(key=lambda i: i['name'])
    return records


def get_unverified():
    """
    Returns all unverified resources.
    """
    records = []
    for record in collection.find({"verified": False}):
        del record['_id']
        records.append(record)
    # Sort the records by name:
    records.sort(key=lambda i: i['name'])
    return records


def del_resource(name):
    """
    Deletes a resource with a specified name from the database.
    """
    for record in collection.find({"name": name}):
        collection.delete_one(record)


def verify_resource(name):
    """
    Marks a resource as verified.
    """
    # for record in collection.find({"name": name}):
    collection.update_one({"name": name},
                          {"$set": {"verified": True}})

    
def interp_bool(boolesque_string):
    if boolesque_string == "yes":
        return True
    if boolesque_string == "N/A":
        return boolesque_string
    return False


def test():
    print("############ TESTING SOME FUNCTIONS ############")
    new = {"website": "http://www.eugenecompletewellness.com/",
    "paperwork_not_only_mf": "",
    "paperwork_asks_for_pronoun": "",
    "notes": "",
    "can_monitor_hormones": True,
    "sliding_scale": "",
    "name": "Rob Voorhees2",
    "email": "info@eugenecompletewellness.com",
    "phone": "541-653-9324",
    "type": "Chiropractor",
    "diversity_aware": "",
    "takes_private_ins": True,
    "takes_OHP": "",
    "office_name": "Eugene Complete Wellness",
    "address": "240 E 12th Ave, Eugene, OR 97401",
           "verified": False}
    collection.insert(new)

    new = {"website": "www.womenscare.com",
    "paperwork_not_only_mf": "No, though they say they are updating this soon",
    "paperwork_asks_for_pronoun": "No.",
    "notes": "",
    "can_monitor_hormones": True,
    "sliding_scale": "",
    "name": "Douglas Austin2",
    "email": "",
    "phone": "541-683-1559",
    "type": "Chiropractor",
    "diversity_aware": "No.",
    "takes_private_ins": True,
    "takes_OHP": False,
    "office_name": "Womens Care",
    "address": "590 Country Club Pkwy B, Eugene, OR 97401",
           "verified": False}
    collection.insert(new)

    # li = get_unverified()
    # for i in li:
    #     print(i)
    verify_resource("Rob Voorhees2")
    verify_resource("Douglas Austin2")
    # print("TEST VERIFY")
    # li = get_unverified()
    # for i in li:
    #     print(i)
    # print("TEST GET Endocrinologist")
    # li = get_db_entries("Endocrinologist", False, True, False)
    # for i in li:
    #     print(i)
    del_resource("Rob Voorhees2")
    del_resource("Douglas Austin2")
    # print("TEST: DELETED")
    # li = get_db_entries("Chiropractor", False, False, False)
    # for i in li:
    #     print(i)


if __name__ == "__main__":
    test() #TODO ERASE
    app.debug = CONFIG.DEBUG
    app.logger.setLevel(logging.DEBUG)
    app.run(port=CONFIG.PORT, host="localhost")
