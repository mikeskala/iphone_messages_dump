import argparse
import glob
import os
import sqlite3
import csv
import json
import sys
from collections import OrderedDict
from datetime import datetime, timedelta

"""
The madrid offset is the offset from 1 Jan 1970 to 1 Jan 2001.
Some database fields use the 2001 format, so it's necessary to
create an offset for these.

Madrid flags in the message table:
NULL: not an iMessage
12289: received
32773: send error
36869, 45061: sent
77825: received message containing parsed data
102405: sent message containing parsed data
"""
MADRID_OFFSET = 978307200
MADRID_FLAGS_SENT = [36869, 45061]


def backup_location(platform):
    mac_names = {"darwin"}
    windows_names = {"win32"}
    if platform in mac_names:
        return "~/Library/Application Support/MobileSync/Backup/*/3d/3d0d7e5fb2ce288813306e4d4636395e047a3d28"
    elif platform in windows_names:
        return "C:/Users/*/AppData/Roaming/Apple Computer/MobileSync/Backup/*/3d/3d0d7e5fb2ce288813306e4d4636395e047a3d28"


class DB():
    def __init__(self, *args, **kwargs):
        self._db = sqlite3.connect(*args, **kwargs)
        self._db.row_factory = self._dict_factory

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def query(self, sql, params=None):
        try:
            c = self._db.cursor()
            c.execute(sql, params or [])
            res = c.fetchall()
            self._db.commit()
        except:
            if self._db:
                self._db.rollback()
            raise

        c.close()
        return res


def extract_messages(db_file):
    db = DB(db_file)
    skipped = 0
    found = 0
    messages = db.query("select * from message")
    message_list = []

    for row in messages:
        timestamp = row['date'] / 1000000000
        is_i_message = 'is_madrid' in row
        if not is_i_message:      # specifies if it's an iMessage or not, value 0 or 1 (0=SMS/MMS, 1=iMessage)
            is_i_message = row['service']
            sent = row['is_sent']
            timestamp += MADRID_OFFSET
        else:
            sent = row['flags'] in [3, 35]
        
        time = datetime.utcfromtimestamp(timestamp)
        time += timedelta(hours=3)                             # UTC + 3 timezone

        # Use text or attributedBody as body depending on whether it's a plain text or rich media message
        # see: https://medium.com/@kellytgold/extracting-imessage-and-address-book-data-b6e2e5729b21
        if row['text'] is not None:
            msg_body = row['text']
        elif row['attributedBody'] is not None: 
            alter_body = row['attributedBody'].decode('utf-8', errors='replace')
            if "NSNumber" in str(alter_body):
                alter_body = str(alter_body).split("NSNumber")[0]
                if "NSString" in alter_body:
                    alter_body = str(alter_body).split("NSString")[1]
                    if "NSDictionary" in alter_body:
                        alter_body = str(alter_body).split("NSDictionary")[0]
                        alter_body = alter_body[6:-12]
                        msg_body = alter_body
        
        if msg_body is None:
            skipped += 1
            continue

        row_data = dict(sent='1' if sent else '0',
                        time = time.strftime(" %d/%m/%Y, %H:%M"),
                        address = row['handle_id'],   # this is the conversation id /group id
                        text = msg_body.replace('\n', '[NL]'),
                        # srvc='iMsg' if is_i_message else 'SMS',
                        # subject=(row['subject'] or ''),
                        guid=row['guid'],
                        )
        message_list.append(row_data)

    print('found {0} skipped {1}'.format(found, skipped))
    return message_list


def compare_files(file_name, message_list):
    message_guid_list = []
    file_guid_list = []
    compared_list = []

    for item in message_list:
        message_guid_list.append(item['guid'])

    if args.output_data == "csv":
        with open(file_name, newline='') as f:
            reader = csv.DictReader(f)
            for item in reader:
                file_guid_list.append(item['guid'])
    elif args.output_data == "json":
        with open(file_name, "r") as f:
            reader = json.load(f)
            for item in reader:
                file_guid_list.append(item['guid'])

    compared_set = set(message_guid_list) - set(file_guid_list)

    for item in message_list:
        if item['guid'] in compared_set:
            compared_list.append(item)

    return compared_list


def get_message_list():
    message_list = []
    pattern = os.path.expanduser(args.input_pattern)
    input_pattern_list = glob.glob(pattern)
    for db_file in input_pattern_list:
        print("reading {0}.".format(db_file))
        messages = extract_messages(db_file)
        for item in messages:
            message_list.append(item)
    return message_list


def set_privacy(message_list):
    """
    Hide values by default for privacy.
    """

    privacy_text = "Text hidden for privacy. Use -p flag to enable text."
    for item in message_list:
        item['text'] = privacy_text


def write_csv(file_object, message_list, ordered_fieldnames, new_file=False):
    writer = csv.DictWriter(file_object, fieldnames=ordered_fieldnames)
    if new_file:
        writer.writeheader()
    rc = wc = 0
    for item in message_list:
        try:
            writer.writerow(item)
            wc += 1
        except ValueError as ex:
            print('Err in Message ', rc, 'skipping it. Text was: ', item['text'], 'Ex:', ex)
        rc += 1
    print('Wrote Message ', wc, 'to file')


def run():
    args.output_file += ".{0}".format(args.output_data)

    field_names = {
        "address": None,    # conversation id
        "sent": None,       # 1 if sent by me
        "time": None,       # of message
        "text": None,       # of message
        "guid": None,       # message id
        # "srvc": None, "subject": None, 
    }
    message_list = get_message_list()
    if args.privacy:
        set_privacy(message_list)
    message_count = len(message_list)
    if os.path.exists(args.output_file):
        compared_list = compare_files(args.output_file, message_list)
        compared_count = len(compared_list)
        if compared_list:
            print("{0} new messages detected. Adding messages to {1}.".format(compared_count, args.output_file))
            if args.output_data == "csv":
                with open(args.output_file, 'a', encoding=args.encoding, newline='') as f:
                    write_csv(f, field_names, compared_list)
            elif args.output_data == "json":
                with open(args.output_file, "r") as r:
                    reader = json.load(r)
                    for item in compared_list:
                        reader.append(item)
                    with open(args.output_file, "w", encoding=args.encoding, newline='') as f:
                        json.dump(message_list, f)

                print(compared_list)
        else:
            print("{0} new messages detected. No messages added.".format(compared_count))
    else:
        print('New file detected. Writing {0} messages to new file at {1}'.format(message_count, args.output_file))
        with open(args.output_file, "w", encoding=args.encoding, newline='') as f:
            if args.output_data == "csv":
                write_csv(f, message_list, field_names, True)
            elif args.output_data == "json":
                with open(args.output_file, "w") as f:
                    json.dump(message_list, f)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert iMessage texts from iPhone backup files to readable data formats."
            "Supported formats include csv and json.")
    parser.add_argument("-d", "--output_data", type=str, default="csv",
            help="The format of data output by the program. csv and json are supported.")
    parser.add_argument("-i", "--input_pattern", type=str, default=backup_location(sys.platform),
            help="The location(s) of your iPhone backup files. Will match patterns according to glob syntax.")
    parser.add_argument("-o", "--output_file", type=str, default=("txt_messages"),
            help="The output file name.")
    parser.add_argument("-s", "--sent_only", action="store_true", default=False,
            help="Output only sent texts. Excludes all other texts.")
    parser.add_argument("-p", "--privacy", action="store_true", default=False,
            help="Enable privacy measures.")
    parser.add_argument("-e", "--encoding", action="store_true", default='utf-8',
            help="Output encoding.")
    args = parser.parse_args()
    run()
