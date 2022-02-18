#!/bin/bash
sudo service docker start
sudo usermod -a -G docker ec2-user
docker ps

# Install Dependencies
pip install redshift-connector

# Configure environment variables
export s3bucket=$1

# START REDSHIFT SETUP WORK
# Parse sample data into processed data and build out the database tables, as well as loading in platforms and marketplaces
python initial_setup.py

# Copy the file with only primary key values to s3
aws s3 cp output.csv s3://$1/ecommerce/ --quiet

# Call on the Redshift data copy query to read the info from S3 into Redshift
python data_loader.py $2
# END REDSHIFT SETUP WORK

