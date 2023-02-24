# Netherlands IND new appointment alerts

# Overview

The IND is the immigration office in the Netherlands. Appointments can be made online to get Biometrics done or pickup Visa documents. There is often a long wait time for appointments. Sooner appointments often open up due to cancellations, but users must keep manually refreshing the page and try to book them before someone else does.

This project allows users to subscribe to push notifications on their phones to receive close to real time alerts when new IND appointments become available.

# Technical Solution Overview

The python code is intended to be hosted on AWS Lambda and scheduled with AWS CloudWatch to run regularly. AlertDefinitions are defined in the script that specify the alert paramters (Appointment type, IND office location, and number of days ahead to include in the alerts). When it runs, appointments are retrieved from the IND API, and push notifications are sent via a 3rd party app called Pushover (pushover.net).

A list of appointments is stored in AWS S3 to keep track of appointments for which alerts have already been sent (because we only want to alert about an appointment when it's new). Each time the process runs any appointments that are in the past are removed from the S3 file to avoid the file becoming larger over time.

# Files

(list the files contained in the repo here and explain what each of them is for)


# Deployment Instructions

Instructions to host the IND Alerts functionality yourself on AWS.

You will need two things:
1. An AWS account - you will need credentials (key and secret) for a user with permissions to read/write to an S3 bucket
2. Sign up for a free account at https://pushover.net/ - here you will create an application to get a user_key and api_token 

Overview of steps:
1. Set up the App in Pushover -> Create an application to generate credentials, download the Pushover app on a mobile device and subscribe to alerts for your application
2. Set up the AWS S3 bucket -> Create a new bucket, upload a .txt file containing "[]" called "master_appts_list"
3. Set up the Lambda function -> Create a Lambda Layer to contain the dependencies (python_libs), Create a Lambda function and upload the .zip file containing the .py files
4. Test and Schedule the Lambda function -> Once manual tests are working, schedule using AWS CloudWatch to run at regular intervals, eg. every 15 minutes


### To generate requirements.txt file from python file (Note: a requirements.txt file is already provided in the repo)
in conda terminal, run:
pip3 install pipreqs
pip3 install pip-tools
cd to project folder (folder that contains .py file)
`pipreqs --savepath=requirements.in` (generates requirements file, .in file extension is needed for next step)
`pip-compile` (gnerates requirements.txt file, includes dependencies of packages from previous step)
The requirements.in file can now be deleted

### To install packages from requirements.txt into the environment (Note: python packages are already provided in the repo)
Run one of these three options to download the packages:
`pip install -r requirements.txt -t .` (this installs all packages into the current directory)
`pip install -r requirements.txt -t ./python` (this installs them into a subdirectory called python - RECOMMENDED)
`pip install -r requirements.txt` (this installs them into the current environment - they will have to be copied from the environment packages folder)

### To install individual packages in the project directory:
cd to directory then run:
`pip3 install <package_name> -t ./`
(This approach is only recommended to use ad hoc for downloading specific packages)

### Use a Layer in AWS Lambda to store the python packages - create the correct .zip file for upload to the Lambda layer
1. create a new empty directory called "python" in the project folder (this folder MUST be called "python")
2. install required packages in this directory using methods described above
3. Zip the python directory recursively. IMPORTANT: to avoid errors in AWS Lambda, the python directory must be zipped recursively. On windows easiest way to do this is using WinRar and use the setting "Put each file to separate archive". If using WinRar make sure to select ZIP as the Archive format. The zip file can be renamed if desired.
4. Create a new Layer in AWS Lambda and upload this zip file to to it
5. Once your Lambda function is created, you will need to associated the Lambda Layer to your Lambda function

# Feature Roadmap

v1 functionality:
- User can subscribe to receive alerts when there are new IND appointments
- Currently there are two types of alerts that can be subscribed to:
    - Document pickup appointments in Amsterdam in the next X days
    - Biometric appointments in Amsterdam in the next X days
- Alerts are in the form of mobile push notifications and are sent via a 3rd party app called Pushover, available on Android and iOS

Future release functionality
- ability to subscribe to alerts for any IND office
- ability to control the time window for which appointment notifications are received eg. next 7 days
