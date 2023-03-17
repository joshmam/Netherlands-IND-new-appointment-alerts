#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# Currently working on:

# Deploy changes again and test -> if working deploy to Lambda prod
# Fully test the experience of subscribing via the link from both iOS and Android device


# In[ ]:


# change log (record changes since last commit)

# moved alert definitions to a json config file
# added function to only store near future appts instead of all future appts


# In[1]:


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

# Establish the AWS file system (for read/write to files in AWS S3)
if is_prod:
    fs = s3fs.S3FileSystem()
    
else:
    awsKey = os.getenv('AWS_KEY')
    awsSecret = os.getenv('AWS_SECRET')
    
    fs = s3fs.S3FileSystem(key=awsKey, secret=awsSecret)


# In[2]:


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
    print(f'new appts not in stored list: {updated_count}')

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
    
    print(f"Total appts returned by API: {len(output)}")
    return output

# Loads .txt file from S3, returns a python list
def load_s3_data(fname):
    with fs.open('s3://ind-appt-alerts/' + fname, 'rb') as f:
        thisFile = f.read() # use eval to remove double quotation marks, otherwise won't load properly
        data = json.loads(thisFile)
    return data

# Saves .txt file to S3, takes python list as data, returns success status as Boolean
def update_s3_data(fname, data):
    try:
        with fs.open('s3://ind-appt-alerts/' + fname, 'w') as f:
            json.dump(data, f)
            success = True
    except:
        success = False
    print(f"saving data to S3 successful: {success}")
    return success

# Remove a specified key from every dict in a list
remove_key = lambda lst, key_to_remove: [{k:v for k, v in d.items() if k != key_to_remove} for d in lst]

# outputs a new appointments list that only contains appointments that are still in the future
def remove_past_appts(input_list, ts_key):
    current_ts = round(datetime.now().timestamp()) # get current timestamp
    return [appt for appt in input_list if appt.get(ts_key) is not None and appt.get(ts_key) >= current_ts]

# outputs a new appointments list that only contains appointments that are still in the future
def remove_far_future_appts(input_list, ts_key, days_ahead_to_keep):
    ts_x_days_ahead = round((datetime.now() + timedelta(days=days_ahead_to_keep)).timestamp())
    return [appt for appt in input_list if appt.get(ts_key) is not None and appt.get(ts_key) <= ts_x_days_ahead]


# In[3]:


# FUNCTION - given an alert definition, determines which appts to send alerts for

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

    stored_appts_list = load_s3_data('master_appts_list.txt')
    print(f'{str(len(stored_appts_list))} stored appointments')

    update_appt_lists(api_all_appts, stored_appts_list, new_appts_list)

    stored_appts_list = remove_key(stored_appts_list, 'dt') # Remove the datetime object from each dict (causing error in json.dump)
    
    stored_appts_minus_past = remove_past_appts(stored_appts_list, 'unix_ts')

    stored_appts_next_x_days_only = remove_far_future_appts(stored_appts_minus_past, 'unix_ts', 14)
    
    update_s3_data('master_appts_list.txt', stored_appts_next_x_days_only)
    print(f'{str(len(stored_appts_next_x_days_only))} appts in stored list after adding near future appts and removing past appts')
    
    # filter new appointments to only next N days (only ones we want to send notifications for)
    appts_to_alert = list(filter(lambda row: dt_in_next_n_days(row['dt'], this_days_ahead), new_appts_list))
    
    print(f'{len(appts_to_alert)} appts to include in ntfn')
    
    return appts_to_alert


# In[4]:


# FUNCTION - creates the message title and body content for the pushover notification given alert definition & list of appts
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


# In[5]:


# FUNCTION - triggers push notification via Pushover given an app_key and user_key or group_key
def send_ntfn(title, msg, api_token, user_key):
    url = "https://api.pushover.net/1/messages.json"

    data = {
        "token": api_token,
        "user": user_key,
        #"device": 'galaxys205g',
        "title": title,
        "message": msg
    }

    response = requests.post(url, data=data)
    return response


# In[6]:


# FUNCTION - runs the entire process given a list of alert definitions

# returns a dict containing the number of ntfn attempts and ntfn successes
def send_push_ntfns(alert_definitions):
    
    alert_definitions_processed = 0
    ntfn_attempts = 0
    ntfn_successes = 0
    
    for this_def in alert_definitions:
    
        appts_to_alert = []
        appts_to_alert = get_appts_to_alert(this_def)
        
        this_pushover_group_key = this_def.pushover_group_key
        this_pushover_app_key = this_def.pushover_app_key

        if len(appts_to_alert) > 0:

            ntfn_content = create_ntfn_content(appts_to_alert, this_def)

            this_resp = send_ntfn(ntfn_content[0], ntfn_content[1], this_pushover_app_key, this_pushover_group_key)
            ntfn_attempts += 1
            
            if this_resp.status_code == 200:
                ntfn_successes += 1
            
        alert_definitions_processed += 1
        
    return {'alert_definitions_processed': alert_definitions_processed, 'ntfn_attempts': ntfn_attempts, 'ntfn_successes': ntfn_successes}


# In[7]:


# retrieve alert definitions from .json file in AWS S3
alert_definitions = load_s3_data("alerts_config.json")


# In[8]:


class AlertDefinition:
    def __init__(self, dict_arg):
        self.__dict__.update(dict_arg)


# In[9]:


alert_definitions_list = []
for d in alert_definitions:
    alert_definitions_list.append( AlertDefinition(d) )


# In[10]:


# Lambda handler function required by AWS Lambda
def lambda_handler(event, context):
    
    response = send_push_ntfns(alert_definitions_list)
    
    if response['ntfn_attempts'] == response['ntfn_successes']:
        status = 200
    else:
        status = 500
    
    return {
        'statusCode': status,
        'body': response
    }


# In[13]:


if not is_prod:
    print("running...")
    lambda_handler(None, None)


# In[12]:


# Use to reset the data in S3 and check it - don't use in Prod
#blank_data = []
#update_s3_data('master_appts_list.txt', blank_data)
#load_s3_data('master_appts_list.txt')

