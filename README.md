# Netherlands IND new appointment alerts

# Overview

The IND is the immigration office in the Netherlands. Appointments can be made online to get Biometrics done or pickup Visa documents. There is often a long wait time for appointments. Sooner appointments sometimes become available due to cancellations, but users must manually refresh the page continually to check for these.

This project allows users to subscribe to push notifications on their mobile devices to receive close to real time alerts when new IND appointments become available.

# Technical Solution Overview

A python script is hosted on AWS Lambda and scheduled with AWS EventBridge to run regularly. Alert Definitions are defined in an alerts_config.json file (Appointment type, IND office location, and number of days ahead to include in the alerts). When the script runs, appointments are retrieved from the IND API, and push notifications are sent via a 3rd party app called Pushover that also handles the alert subscriptions.

A list of appointments is stored in AWS S3 to keep track of appointments for which alerts have already been sent (because we only want to alert about an appointment when it's new). Each time the process runs, any appointments that are in the past are removed from the S3 file to avoid the file becoming larger over time.

# Components

Repo files:

* IND_appointment_ntfns.py -> Python script that checks for new appointments and generates the alerts, contains the lambda function for AWS Lambda.
* alerts_config_example.json -> Example format of how to configure alerts including the credentials for AWS and Pushover. This file should be renamed to alerts_config.json before it is deployed.
* master_appts_list.txt -> Text file containin an empty list to be uploaded to AWS S3. This is where the python script stores existing IND appointments.
* requirements.txt -> For installing all the dependencies (python packages) of the python script

Solution Components:

* Pushover.net -> 3rd party service used to send the push notifications and handle the subsriptions of mobile devices to the alerts through the Pushover app on iOS or Android
* AWS -> The cloud computing platform used to host the alert system. This project utilises AWS Lambda, AWS S3, and AWS EventBridge.


# Deployment Instructions

***Instructions on how to host the IND Alerts functionality yourself on AWS using this repo.***

### You will need three things:
1. A copy of this repo
2. An AWS account - you will need credentials (key and secret) for a user with permissions to read/write to an S3 bucket
3. Sign up for a free account at https://pushover.net/ - here you will create an App (to get an API Key), and link it to a Delivery Group (to get a Delivery Group Key). A separate App & Delivery Group pair needs to be created for every Alert Definition that's defined in alerts_config.json

### Setup steps:
1. At pushover.net, create a free account, then create an App, then create a Delivery Group, then in the App -> Subscription Settings -> Subcription Type, select the Delivery Group and save. Save the API Key and Group Key that are generated.
2. Create an AWS account, create a new user with the required permissions and save the user key and secret
3. In the alerts_config.json file, create an Alert definition by specifying the parameters and credentials according to the format shown in the example file.
4. Use requirements.txt and a package manager such as pip to download all the dependencies to your project folder.
5. Upload the final alerts_config.json file and the master_appts_list.txt file to an AWS S3 bucket, ensuring that the bucket name matches the bucket name referenced in the .py file.
6. Set up the Lambda function. Create a Lambda Layer where you'll upload all the dependencies to. Create a Lambda Function and upload a .zip file that contains the .py file. Ensure the Lambda Function is linked to the Lambda Layer you created. Test by running it manually.
7. Schedule the Lambda Function using AWS EventBridge. The Lambda Function will check for new appointments every time it runs, so set it to a regular interval such as every 5 minutes or 15 minutes.

# Feature Roadmap

### v1 functionality:
- User can subscribe to receive alerts when there are new IND appointments
- Currently there are two types of alerts that can be subscribed to:
    - Document pickup appointments in Amsterdam in the next 3 days
    - Biometric appointments in Amsterdam in the next 3 days
- Alerts are in the form of mobile push notifications and are sent via a 3rd party app called Pushover, available on Android and iOS

### Future release functionality:
- includ a link to the IND website with each alert to make it easier to book directly from the alert
- ability for user to subscribe to alerts for any IND office
- ability for user to control the time window for which appointment notifications are received eg. next 7 days

# Appendix - installing dependencies & Lambda layer setup

## To install packages from requirements.txt into the environment
Run this command from your local project directory:
`pip install -r requirements.txt -t ./python` (this installs all the dependencies into a subdirectory called python)

## Use a Layer in AWS Lambda to store the python packages - create the correct .zip file for upload to the Lambda layer
1. Run the command mentioned above that creates a "python" folder and install all the dependencies into it.
2. Zip the python directory recursively. IMPORTANT: For the Layer to work in AWS Lambda, the python directory must be zipped recursively. On windows, the easiest way to do this is using WinRar and use the setting "Put each file to separate archive". If using WinRar make sure to select ZIP as the Archive format. The zip file can be renamed if desired.
4. Create a new Layer in AWS Lambda and upload this zip file to it.
5. Once your Lambda function is created, you will need to associate this Lambda Layer to your Lambda function.