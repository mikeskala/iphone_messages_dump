iphone_messages_dump
====================

A python script to dump iMessage data (text and metadata) from an iPhone backup to a file.
Handles several output data formats including csv, txt and json.
Usage:
1. Connect your iPhone to a computer and make a backup using iTunes
2. Run this script using Python (command line) to export your text iMessages and SMS.
  Some usage examples:
> python iphone_messages_dump.py
> python iphone_messages_dump.py -f txt -o my_dump_file


Originally based on Jehiah Czebotar's script to dump iMessages to a csv file.

This script now runs on Python 3 and fixes several bugs.

See the iphonewiki for more information on how this script works. http://theiphonewiki.com/wiki/IMessage#References

TODO:

- Proper error handling for Madrid flags 32773, 77825, 102405.
- Unit tests with Nose.
- Refactor csv / json if else handling


List of done:

- Forked from: https://github.com/echohack/iphone_messages_dump
- Better unicode handling: use utf-8 encoding (to support messages in hebrew)
- Skip message with empty 'text' field
- Output choice: Add support for TXT.
- Filter messages by group-id
- 

