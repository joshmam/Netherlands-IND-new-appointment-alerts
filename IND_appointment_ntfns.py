#!/usr/bin/env python
# coding: utf-8

# In[1]:


# Currently working on:

# Deploy changes again and test -> if working deploy to Lambda prod
# Fully test the experience of subscribing via the link from both iOS and Android device

# Make location and type into proper names


# In[24]:


# Define an Alert Definition object - used to specify the alerts we want to receive
class AlertDefinition:
    def __init__(self, appt_type, appt_location, days_ahead_to_alert, pushover_delivery_group_key):
        self.appt_type = appt_type
        self.appt_location = appt_location
        self.days_ahead_to_alert = days_ahead_to_alert
        self.pushover_delivery_group_key = pushover_delivery_group_key
    
    def __str__(self):
        return f"Alert for {self.appt_type} appointments in {self.appt_location} within next {self.days_ahead_to_alert} days."
    
    def __repr__(self):
        return f"AlertDefinition('{self.appt_type}', '{self.appt_location}', {self.days_ahead_to_alert})"


########################
### INPUT PARAMATERS ###
########################
    
# Create instances of the AlertDefinition object and put in a list
alert1 = AlertDefinition('BIO', 'AM', 3, 'giocwtmbeg22ohkabi62sjc7p2zimx')
alert2 = AlertDefinition('DOC', 'AM', 3, 'gpa97esivhizkjhip9exvtogkt5gfj')

alert_definition_list = [alert1, alert2]


# In[3]:


# Print out the alert definitions

print(f'{len(alert_definition_list)} Alert Definition(s) have been defined\n---------------------------------------')
for a in alert_definition_list:
    print(a)


# In[4]:


# IMPORT PACKAGES AND CONFIGURATION

import requests
import json
from datetime import datetime, timedelta
import s3fs
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import os

# Dev or Prod
is_prod_str = os.getenv('IS_PROD')
is_prod = is_prod_str.upper() == "TRUE"

# Load credentials
api_token_pushover = os.getenv('PUSHOVER_API_TOKEN')
#user_key_pushover = os.getenv('PUSHOVER_USER_KEY')

# Establish the AWS file system (for read/write to files in AWS S3)
if is_prod:
    fs = s3fs.S3FileSystem()
    
else:
    awsKey = os.getenv('AWS_KEY')
    awsSecret = os.getenv('AWS_SECRET')
    
    fs = s3fs.S3FileSystem(key=awsKey, secret=awsSecret)


# In[5]:


# FUNCTIONS

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
    print(f'{updated_count} new appointments found')

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
def load_s3_data(fname):
    with fs.open('s3://ind-appt-alerts/' + fname + '.txt', 'rb') as f:
        thisFile = f.read() # use eval to remove double quotation marks, otherwise won't load properly
        data = json.loads(thisFile)
    return data

# Saves .txt file to S3, takes python list as data, returns success status as Boolean
def update_s3_data(fname, data):
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


# In[6]:


# FUNCTION THAT DETERMINES APPOINTMENTS TO SEND ALERTS ABOUT

# Gets any new appointments for the specified appointment type, location, and number of days into the future (days_ahead)
# Returns a list of appointments we send alerts for
def get_appts_to_alert(alert_definition):
    this_appt_type = alert_definition.appt_type
    this_appt_loc = alert_definition.appt_location
    this_days_ahead = alert_definition.days_ahead_to_alert
    
    new_appts_list = [] # will contain all new appointments found in the API response data
    stored_appts_list = [] # all appointments, stored in S3, so we don't notify about the same appointment twice
    appts_to_alert = [] # only upcoming appointments that we want to send alerts for
    
    print(f'commencing for alert definition "{alert_definition}"')
    
    api_all_appts = None
    api_all_appts = get_apps(this_appt_type, this_appt_loc)

    # convert all date params in the list to datetimes
    create_dt(api_all_appts)

    stored_appts_list = load_s3_data('master_appts_list')
    print(f'{str(len(stored_appts_list))} stored appointments')

    update_appt_lists(api_all_appts, stored_appts_list, new_appts_list)

    stored_appts_list = remove_key(stored_appts_list, 'dt') # Remove the datetime object from each dict (causing error in json.dump)
    all_future_appts = remove_past_appts(stored_appts_list, 'unix_ts') # Remove any appointments in the past before saving (to keep file size small)
    update_s3_data('master_appts_list', all_future_appts)
    print(f'{str(len(all_future_appts))} appts in stored list after adding new appts and removing past appts')
    
    # filter new appointments to only next N days (only ones we want to send notifications for)
    appts_to_alert = list(filter(lambda row: dt_in_next_n_days(row['dt'], this_days_ahead), new_appts_list))
    
    print(f'{len(appts_to_alert)} appts to include in ntfn')
    
    return appts_to_alert


# In[16]:


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
        msg_title = f'{str(msg_count)} new IND appts for ' + this_appt_type + ' at ' + this_appt_loc + ', here are next 3 times:'
        
    return msg_title, msg_string


# In[8]:


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


# In[9]:


# Sends the alerts via Pushover, given the list of Alert Definitions, if there are any alerts to send
# returns a dict containing the number of ntfn attempts and ntfn successes
def send_push_ntfns(alert_definitions):
    
    alert_definitions_processed = 0
    ntfn_attempts = 0
    ntfn_successes = 0
    
    for this_def in alert_definitions:
    
        appts_to_alert = []
        appts_to_alert = get_appts_to_alert(this_def)
        
        this_pushover_key = this_def.pushover_delivery_group_key

        if len(appts_to_alert) > 0:

            ntfn_content = create_ntfn_content(appts_to_alert, this_def)

            this_resp = send_ntfn(ntfn_content[0], ntfn_content[1], api_token_pushover, this_pushover_key)
            ntfn_attempts += 1
            
            if this_resp.status_code == 200:
                ntfn_successes += 1
            
        alert_definitions_processed += 1
        
    return {'alert_definitions_processed': alert_definitions_processed, 'ntfn_attempts': ntfn_attempts, 'ntfn_successes': ntfn_successes}


# In[10]:


# Lambda handler function required by AWS Lambda
def lambda_handler(event, context):
    
    response = send_push_ntfns(alert_definition_list)
    
    if response['ntfn_attempts'] == response['ntfn_successes']:
        status = 200
    else:
        status = 500
    
    return {
        'statusCode': status,
        'body': response
    }


# In[30]:


if not is_prod:
    print("running...")
    lambda_handler(None, None)


# In[29]:


# Use to reset the data in S3 and check it - don't use in Prod
#blank_data = []
#update_s3_data('master_appts_list', blank_data)
#load_s3_data('master_appts_list')


# In[ ]:




