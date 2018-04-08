
import logging
import flask  # Web server tool.
import arrow  # For times and times.
from pymongo import MongoClient  # Mongo database
import re
import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir) 

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

####
# Database connection per server process
###
try:
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, str(CONFIG.DB))
    collection = db.resources
    users_collection = db.users
except:
    print("Failure opening database. Is Mongo running? Correct password?")
    sys.exit(1)

# Care Provider Category
# Provider Name
# Office/Clinic Name (if applicable)
# Address
# Phone
# Email
# Web address
# Do they take Oregon Health Plan (OHP)?
# Do they take private insurance?
# Sliding Scale Option?
# Has staff received Gender Diversity Awareness Training?
# Does intake or chart paperwork include more options than M or F?
# Does paperwork ask for pronoun?
# Can Monitor Hormones?
# Notes
def create(line):
    print(len(info))
    print(info)
    new = {"type": info[0],
           "name": info[1],
           "office_name": info[2],
           "address": info[3],
           "phone": info[4],
           "email": info[5],
           "website": info[6],
           "takes_OHP": info[7],
           "takes_private_ins": info[8],
           "sliding_scale": info[9],
           "diversity_aware": info[10],
           "paperwork_not_only_mf": info[11],
           "paperwork_asks_for_pronoun": info[12],
           "can_monitor_hormones": info[13],
           "notes": info[14],
           "verified": True
           }
    res = collection.insert(new)
    if hasattr(res, "writeConcernError"):
        app.logger.debug(res["writeConcernError"])
        return False
    elif hasattr(res, "writeError"):
        app.logger.debug(res["writeError"])
        return False
    else:
        return True

input = sys.stdin.read().split("\n")
total = len(input)
i = 1
while i < total:
    for char in input[i]:
        if char == '\t' or char == '' or char == '\r':
            continue
        print(input[i])
        info = re.split(r'\t+', input[i].rstrip('\t'))
        while len(info) < 14:
            i+=1
            more = re.split(r'\t+', input[i].rstrip('\t'))
            info[-1] += more[0]
            more.remove(more[0])
            info.extend(more)
        create(info)
        break
    i+=1
