import pymongo
import argparse
from bson import ObjectId

# Define the MongoDB connection
client = pymongo.MongoClient("mongodb://localhost:27017/")  # Update the connection string if needed
db = client['streammon']

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Update MongoDB schema with dry-run option")
parser.add_argument('--dry-run', action='store_true', help="Run the script without making any changes")
args = parser.parse_args()

# Check schema version
global_configs = db.global_configs.find_one()
try:
    schema_version = global_configs.get('schema_version', 0)
except AttributeError:
    print("Schema version not found in global_configs. Setting to 0.")
    schema_version = 0

# Define the required schema version threshold
REQUIRED_SCHEMA_VERSION = 1

if schema_version < REQUIRED_SCHEMA_VERSION:
    print(f"Updating schema to version {REQUIRED_SCHEMA_VERSION}")

    # Update stream_configs collection
    print("stream_configs collection: ")
    stream_configs = db.stream_configs.find()
    for config in stream_configs:
        if '_id' in config:
            stream_id_str = str(config['_id'])
            if args.dry_run:
                print(f"Dry-run: Would set streamId for _id {config['_id']} to {stream_id_str}")
            else:
                print(f"Setting streamId for _id {config['_id']} to {stream_id_str}")
                db.stream_configs.update_one(
                    {'_id': config['_id']},
                    {'$set': {'streamId': stream_id_str}}
                )

    # Update the stream_alerts collection
    # here we will match the value of "stream" with the "title" field in stream_configs,
    # and then copy the streamId from stream_configs to stream_alerts
    print ("stream_alerts collection: ")
    stream_alerts = db.stream_alerts.find()
    for alert in stream_alerts:
        if 'stream' in alert:
            stream_config = db.stream_configs.find_one({'title': alert['stream']})
            if stream_config:
                stream_id_str = str(stream_config['_id'])
                if args.dry_run:
                    print(f"Dry-run: Would set streamId for stream {alert['stream']} to {stream_id_str}")
                else:
                    print(f"Setting streamId for stream {alert['stream']} to {stream_id_str}")
                    db.stream_alerts.update_one(
                        {'_id': alert['_id']},
                        {'$set': {'streamId': stream_id_str}}
                    )
            else:
                print(f"Stream {alert['stream']} not found in stream_configs")


    # Update the stream_images collection
    # here we will match the value of "stream" with the "title" field in stream_configs,
    # and then copy the streamId from stream_configs to stream_images
    stream_images = db.stream_images.find()
    print ("stream_images collection: ")
    for image in stream_images:
        if 'stream' in image:
            stream_config = db.stream_configs.find_one({'title': image['stream']})
            if stream_config:
                stream_id_str = str(stream_config['_id'])
                if args.dry_run:
                    print(f"Dry-run: Would set streamId for stream {image['stream']} to {stream_id_str}")
                else:
                    print(f"Setting streamId for stream {image['stream']} to {stream_id_str}")
                    db.stream_images.update_one(
                        {'_id': image['_id']},
                        {'$set': {'streamId': stream_id_str}}
                    )
            else:
                print(f"Stream {image['stream']} not found in stream_configs")

    # Update the stream_reports collection
    # here we will match the value of "title" with the "title" field in stream_configs,
    # and then copy the streamId from stream_configs to stream_reports
    stream_reports = db.stream_reports.find()
    print ("stream_reports collection: ")
    for report in stream_reports:
        if 'title' in report:
            stream_config = db.stream_configs.find_one({'title': report['title']})
            if stream_config:
                stream_id_str = str(stream_config['_id'])
                if args.dry_run:
                    print(f"Dry-run: Would set streamId for report {report['title']} to {stream_id_str}")
                else:
                    print(f"Setting streamId for report {report['title']} to {stream_id_str}")
                    db.stream_reports.update_one(
                        {'_id': report['_id']},
                        {'$set': {'streamId': stream_id_str}}
                    )
            else:
                print(f"Stream {report['title']} not found in stream_configs")

    # Update users collection
    print("users collection: ")
    users = db.users.find()
    for user in users:
        if '_id' in user:
            user_id_str = str(user['_id'])
            if args.dry_run:
                print(f"Dry-run: Would set userId for _id {user['_id']} to {user_id_str}")
            else:
                print(f"Setting userId for _id {user['_id']} to {user_id_str}")
                db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'userId': user_id_str}}
                )

    if not args.dry_run:
        # Update the schema version in global_configs
        print(f"Updating schema version to {REQUIRED_SCHEMA_VERSION}")

        db.global_configs.update_one(
            {'_id': global_configs['_id']},
            {'$set': {'schema_version': REQUIRED_SCHEMA_VERSION}},
            upsert=True
        )

    print("Schema update complete." if not args.dry_run else "Dry-run complete.")
else:
    print("No schema update needed. Current schema version:", schema_version)
