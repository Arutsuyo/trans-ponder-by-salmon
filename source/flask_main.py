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
import arrow  # For times and times.
from pymongo import MongoClient  # Mongo database
import config  # Get config settings from credentials file

####
# App globals.
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

app = flask.Flask(__name__)
app.secret_key = CONFIG.SECRET_KEY


####
# Database connection per server process
###
try:
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, str(CONFIG.DB))
    collection = db.resources
except:
    print("Failure opening database. Is Mongo running? Correct password?")
    sys.exit(1)


###
# Pages
###
# Main index page
@app.route("/")
@app.route("/index")
def index():
    app.logger.debug("Main page entry")
    return flask.render_template('index.html')


# A function to display resources to the front end from the db.
@app.route("/_disp")
def disp():
    filter_ohp, filter_monitor_hormones, filter_pvt_ins = False, False, False
    # resource_type = flask.request.args.get('resource_type')
    # app.logger.debug("Pulling resources of type: " + resource_type)
    resource_type = 0  # TODO temp
    result = {"resources": get_db_entries(resource_type, filter_ohp, filter_monitor_hormones, filter_pvt_ins)}
    return flask.jsonify(result=result)


# Function to add a new resource to the db:
@app.route("/_create")
def create():
    app.logger.debug("Uploading new resource to db.")
    # Get resource contents from user.
    website = flask.request.args.get('website')
    paperwork_not_only_mf = flask.request.args.get('paperwork_not_only_mf')
    paperwork_asks_for_pronoun = flask.request.args.get('paperwork_asks_for_pronoun')
    notes = flask.request.args.get('notes')
    can_monitor_hormones = flask.request.args.get('can_monitor_hormones')
    sliding_scale = flask.request.args.get('sliding_scale')
    name = flask.request.args.get('name')
    email = flask.request.args.get('email')
    phone = flask.request.args.get('phone')
    type = flask.request.args.get('type')
    diversity_aware = flask.request.args.get('diversity_aware')
    takes_private_ins = flask.request.args.get('takes_private_ins')
    takes_ohp = flask.request.args.get('takes_OHP')
    office_name = flask.request.args.get('office_name')
    address = flask.request.args.get('address')

    # Add a new entry to the database with the contents submitted by the user.
    new = {"website": website,
           "paperwork_not_only_mf": paperwork_not_only_mf,
           "paperwork_asks_for_pronoun": paperwork_asks_for_pronoun,
           "notes": notes,
           "can_monitor_hormones": can_monitor_hormones,
           "sliding_scale": sliding_scale,
           "name": name,
           "email": email,
           "phone": phone,
           "type": type,
           "diversity_aware": diversity_aware,
           "takes_private_ins": takes_private_ins,
           "takes_OHP": takes_ohp,
           "office_name": office_name,
           "address": address,
           "verified": False}
    collection.insert(new)

    # Return to the resources:
    filter_ohp, filter_monitor_hormones, filter_pvt_ins = False, False, False
    # resource_type = flask.request.args.get('resource_type')
    # app.logger.debug("Pulling resources of type: " + resource_type)
    resource_type = 0  #TODO temp
    result = {"resources": get_db_entries(resource_type, filter_ohp, filter_monitor_hormones, filter_pvt_ins)}
    return flask.jsonify(result=result)


# Delete a resource
@app.route("/_del")
def delete():
    # Get the name of the resource to delete from user:
    name = flask.request.args.get('name')
    app.logger.debug("Deleting resource")
    del_resource(name)

    # Return to the remaining resources:

    filter_ohp, filter_monitor_hormones, filter_pvt_ins = False, False, False
    # resource_type = flask.request.args.get('resource_type')
    # app.logger.debug("Pulling resources of type: " + resource_type)
    resource_type = 0  #TODO temp
    result = {"resources": get_db_entries(resource_type, filter_ohp, filter_monitor_hormones, filter_pvt_ins)}
    return flask.jsonify(result=result)


# Get unverified resources.
@app.route("/_unverified")
def unverified():
    # This page should only be accessible to volunteer
    # users such that they can go through unverified
    # resources and mark them verified or delete
    # them as appropriate.
    result = {"resources": get_unverified()}
    return flask.jsonify(result=result)


# verify a resource
@app.route("/_verify")
def verify():
    # Get the name of the resource to verify from user input:
    name = flask.request.args.get('name')
    app.logger.debug("verifying resource")
    verify_resource(name)
    # Return to the remaining unverified resources:
    result = {"resources": get_unverified()}
    return flask.jsonify(result=result)


# Error page(s).
@app.errorhandler(404)
def page_not_found(error):
    app.logger.debug("Page not found")
    return flask.render_template('page_not_found.html',
                                 badurl=flask.request.base_url,
                                 linkback=flask.url_for("index")), 404


##############
# Functions available to the page code above
##############
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
        if filter_ohp and record["takes_OHP"] is not True:
            matching_record = False
        if filter_monitor_hormones and record["can_monitor_hormones"] is not True:
            matching_record = False
        if filter_pvt_ins and record["takes_private_ins"] is not True:
            matching_record = False
        if matching_record:
            records.append(record)
    # Sort the records by arrow date:
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
    # Sort the records by arrow date:
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
                          {"$set": {"verified": True }})


def test():
    print("TESTING SOME FUNCTIONSSSSSSSSSSSSSSSs")
    new = {"website": "http://www.eugenecompletewellness.com/",
    "paperwork_not_only_mf": "",
    "paperwork_asks_for_pronoun": "",
    "notes": "",
    "can_monitor_hormones": True,
    "sliding_scale": "",
    "name": "Rob Voorhees",
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
    "name": "Douglas Austin",
    "email": "",
    "phone": "541-683-1559",
    "type": "Endocrinologist",
    "diversity_aware": "No.",
    "takes_private_ins": True,
    "takes_OHP": False,
    "office_name": "Womens Care",
    "address": "590 Country Club Pkwy B, Eugene, OR 97401",
           "verified": False}
    collection.insert(new)

    li = get_unverified()
    for i in li:
        print(i)
    verify_resource("Rob Voorhees")
    verify_resource("Douglas Austin")
    print("TEST VERIFY")
    li = get_unverified()
    for i in li:
        print(i)
    print("TEST GET Endocrinologist")
    li = get_db_entries("Endocrinologist", False, True, False)
    for i in li:
        print(i)
    del_resource("Rob Voorhees")
    del_resource("Douglas Austin")
    print("TEST: DELETED")
    li = get_db_entries("Chiropractor", False, False, False)
    for i in li:
        print(i)


if __name__ == "__main__":
    test()
    app.debug = CONFIG.DEBUG
    app.logger.setLevel(logging.DEBUG)
    app.run(port=CONFIG.PORT, host="localhost")
