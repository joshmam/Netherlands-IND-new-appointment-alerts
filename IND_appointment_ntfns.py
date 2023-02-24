#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# Currently working on:

# Make readme good enough for initial commit
# Download Dotenv package and add to Lambda Layer
# Two functions in Lambda -> staging & prod, test of latest version in staging
# Initial commit to Github


# ### To do
# 
# - Setup Github Actions with AWS Lambda to remove need for manually deploying changes
# - change appointment type and location to use full names in alerts to be more descriptive
# - test subscribing from iOS device

# In[40]:


# Define an Alert Definition object - used to specify the alerts we want to receive
class AlertDefinition:
    def __init__(self, appt_type, appt_location, days_ahead_to_alert):
        self.appt_type = appt_type
        self.appt_location = appt_location
        self.days_ahead_to_alert = days_ahead_to_alert

    def get_days_ahead_to_alert(self):
        return self.days_ahead_to_alert
    
    def get_days_ahead_to_alert(self):
        return self.days_ahead_to_alert
    
    def __str__(self):
        return f"Alert for {self.appt_type} appointments in {self.appt_location} within next {self.days_ahead_to_alert} days."
    
    def __repr__(self):
        return f"AlertDefinition('{self.appt_type}', '{self.appt_location}', {self.days_ahead_to_alert})"


########################
### INPUT PARAMATERS ###
########################
    
# Create instances of the AlertDefinition object and put in a list
alert1 = AlertDefinition('BIO', 'AM', 3)
alert2 = AlertDefinition('DOC', 'AM', 3)

alert_definition_list = [alert1, alert2]


# In[41]:


# Print out the alert definitions

print(f'{len(alert_definition_list)} Alert Definition(s) have been defined\n---------------------------------------')
for a in alert_definition_list:
    print(a)


# In[42]:


# IMPORT PACKAGES AND CONFIGURATION

import requests
import json
from datetime import datetime, timedelta
import s3fs
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import os

# Load credentials
api_token_pushover = os.getenv('PUSHOVER_API_TOKEN')
user_key_pushover = os.getenv('PUSHOVER_USER_KEY')

awsKey = os.getenv('AWS_KEY')
awsSecret = os.getenv('AWS_SECRET')

# Establish the AWS file system (for read/write to files in AWS S3)
fs = s3fs.S3FileSystem(key=awsKey, secret=awsSecret)


# In[43]:


# DEFINE PRELIMINARY FUNCTIONS

# Checks if item is already in the list, returns Boolean
def is_in_list(item, lst):
    in_list = list(filter(lambda row: row['key'] == item['key'], lst))
    return True if len(in_list) > 0 else False

# Adds new items to lists
def update_appt_lists(recent_output, master_list, new_appts):
    updated_count = 0
    for i in recent_output:
        if is_in_list(i, master_list) == False:
            master_list.append(i) # master_list contains all historical appointments
            new_appts.append(i) # new_appts only contains new appointemnts that weren't in master list
            updated_count += 1
    return updated_count

# adds two new keys to each dict in list of dicts, given date string, adds datetime and unix timestamp
def create_dt(lst):
    for i in lst:
        this_dt = None
        this_dt = datetime.strptime(i['date'], '%Y-%m-%d')
        i['dt'] = this_dt
        i['unix_ts'] = int(datetime.timestamp(this_dt))
        
# checks whether a datetime is within the next n days, returns Boolean
def dt_in_next_n_days(some_datetime, n_days):
    now = datetime.now()
    future_time = now + timedelta(days=n_days)
    return some_datetime <= future_time

# Gets the raw appointmnet data from IND given appointment type and location
def get_apps(app_type, app_loc):
    url = 'https://oap.ind.nl/oap/api/desks/' + app_loc + '/slots/?productKey=' + app_type + '&persons=1'
    resp_raw = requests.get(url)
    resp_bytes = resp_raw.content
    resp_str = resp_bytes.decode('utf-8')
    
    # remove first 5 characters and the last char of the string to make it valid json (issue with data from IND's API)
    clean_str = resp_str[28:-1]
    
    output = json.loads(clean_str)
    
    return output

# Loads .txt file from S3, returns a python list
def LoadData(fname):
    with fs.open('s3://ind-appt-alerts/' + fname + '.txt', 'rb') as f:
        thisFile = f.read() # use eval to remove double quotation marks, otherwise won't load properly
        data = json.loads(thisFile)
    return data

# Saves .txt file to S3, takes python list as data, returns success status as Boolean
def SaveData(fname, data):
    try:
        with fs.open('s3://ind-appt-alerts/' + fname + '.txt', 'w') as f:
            json.dump(data, f)
            success = True
    except:
        success = False
    return success

# Remove a specified key from every dict in a list
remove_key = lambda lst, key_to_remove: [{k:v for k, v in d.items() if k != key_to_remove} for d in lst]

# outputs a new appointments list that only contains appointments that are still in the future
def remove_past_appts(lst, ts_key):
    current_ts = round(datetime.now().timestamp()) # get current timestamp
    filtered_lst = [i for i in lst if i.get(ts_key) != None if i.get(ts_key) > current_ts]
    return filtered_lst


# In[44]:


# FUNCTION THAT DETERMINES APPOINTMENTS TO SEND ALERTS ABOUT

# Gets any new appointments for the specified appointment type, location, and number of days into the future (days_ahead)
# Returns a list of appointments we send alerts for
def get_appts_to_alert(alert_definition):
    this_appt_type = alert_definition.appt_type
    this_appt_loc = alert_definition.appt_location
    this_days_ahead = alert_definition.days_ahead_to_alert
    
    # set lists to empty
    new_appts_list = [] # will contain all new appointments found in the API response data
    master_appts_list = [] # all appointments, stored in S3, so we don't notify about the same appointment twice
    appts_to_alert = [] # only upcoming appointments that we want to send alerts for
    
    print('PROCESSING: ' + str(alert_definition))
    
    # Get latest appointments list from IND API
    this_output = None
    this_output = get_apps(this_appt_type, this_appt_loc)

    # convert all date params in the list to datetimes
    create_dt(this_output)

    ##### RETRIEVE MASTER LIST FROM STORAGE
    master_appts_list = LoadData('master_appts_list')
    
    # print out length of lists - before updating
    print(f' - There are {str(len(master_appts_list))} appointments in master list BEFORE updating')

    # update appointments lists
    update_count = update_appt_lists(this_output, master_appts_list, new_appts_list)
    print(f' - {update_count} new appointments found')

    # print out length of lists - after updating
    print(f' - There are now {str(len(master_appts_list))} appointments in master list')
    print(f' - There are now {str(len(new_appts_list))} appointments in new appts list')

    ##### UPDATE MASTER LIST IN STORAGE
    master_appts_list = remove_key(master_appts_list, 'dt') # Remove the datetime object from each dict (causing error in json.dump)
    master_appts_list_excl_past = remove_past_appts(master_appts_list, 'unix_ts') # Remove any appointments in the past before saving (to keep file size small)
    print(f' - There are now {str(len(master_appts_list_excl_past))} appts in master list after removing past appts')
    
    SaveData('master_appts_list', master_appts_list_excl_past)
    
    # filter new appointments to only next N days (only ones we want to send notifications for)
    appts_to_alert = list(filter(lambda row: dt_in_next_n_days(row['dt'], this_days_ahead), new_appts_list))
    
    print(f' - There are {len(appts_to_alert)} appointments to alert about')
    
    return appts_to_alert


# In[45]:


# Creates the message title and body content for the pushover notification
def create_ntfn_content(appts_list, alert_definition):
    this_appt_type = alert_definition.appt_type
    this_appt_loc = alert_definition.appt_location
    
    msg_list = []
    msg_title = None
    msg_content = None
    
    # create a message string for each appointment in appts_list and store in new list
    msg_list = list(map(lambda i: "Appt time: " + i['date'] + " at " + i['startTime'], appts_list))
    msg_count = len(msg_list)
    
    # join list of messages into single string with line breaks
    delimiter = '\n'
    msg_string = delimiter.join(msg_list[:3])
        
    if msg_count == None:
        return None
    elif msg_count <= 3:
        msg_title = f'{str(msg_count)} new IND appts for ' + this_appt_type + ' at ' + this_appt_loc + ':'
    else:
        msg_title = f'{str(msg_count)} new IND appts for ' + this_appt_type + ' at ' + this_appt_loc + ', first 3 shown:'
        
    return msg_title, msg_string


# In[46]:


# Sends a push notification by making request to Pushover API, returns the API response
def send_ntfn(title, msg, api_token, user_key):
    url = "https://api.pushover.net/1/messages.json"

    data = {
        "token": api_token,
        "user": user_key,
        "device": 'galaxys205g',
        "title": title,
        "message": msg
    }

    response = requests.post(url, data=data)
    return response


# In[47]:


# Sends the alerts via Pushover, given the list of Alert Definitions, if there are any alerts to send
# returns a dict containing the number of ntfn attempts and ntfn successes
def checkAndSendAlerts(AlertDefinitionList):
    
    ntfn_attempts = 0
    ntfn_successes = 0
    
    for a in AlertDefinitionList:
    
        # get list of upcoming appts to alert about
        appts_to_alert = get_appts_to_alert(a)

        if len(appts_to_alert) > 0:

            # create the notification content
            ntfn_content = create_ntfn_content(appts_to_alert, a)

            # send notification to Pushover
            this_resp = send_ntfn(ntfn_content[0], ntfn_content[1], api_token_pushover, user_key_pushover)
            ntfn_attempts += 1
            if this_resp.status_code == 200: ntfn_successes += 1
            
    return {'ntfn_attempts': ntfn_attempts, 'ntfn_successes': ntfn_successes}


# In[48]:


# Lambda handler function required by AWS Lambda
def lambda_handler(event, context):
    
    response = checkAndSendAlerts(alert_definition_list)
    
    if response['ntfn_attempts'] == response['ntfn_successes']:
        status = 200
    else:
        status = 500
    
    return {
        'statusCode': status,
        'body': response
    }


# In[ ]:


### DELETE EVERYTHING BELOW HERE WHEN DEPLOYED IN LAMBDA
lambda_handler(None, None)


# In[ ]:


# Use to reset the data in S3 and check it - don't use in Prod
#blank_data = []
#SaveData('master_appts_list', blank_data)
#LoadData('master_appts_list')

