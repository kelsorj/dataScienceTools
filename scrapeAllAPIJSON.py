import os
import json
from pymongo import MongoClient

# Constants
BASE_DIRECTORY = "E:\\AllAPIJSON"
FILE_PATTERN = ".json"

# Connect to the local MongoDB instance
client = MongoClient('localhost', 27017)
db = client.mydb
collection = db.AllAPIJSON

def insert_json_to_mongodb(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Inserting the JSON data into the MongoDB collection
        collection.insert_one(data)

def crawl_and_insert():
    # Walk through directory
    for dirpath, dirnames, filenames in os.walk(BASE_DIRECTORY):
        # Filter out only the JSON files
        json_files = [f for f in filenames if f.endswith(FILE_PATTERN)]
        for filename in json_files:
            file_path = os.path.join(dirpath, filename)
            insert_json_to_mongodb(file_path)
            print(f"Inserted records from: {file_path}")

if __name__ == "__main__":
    crawl_and_insert()
