import tomllib
import os
from logging import getLogger

from opt_gap_check import transfer_data

logger = getLogger(__name__)

def get_config():
    with open("opt_gap_config.toml", "rb") as f:
        data = tomllib.load(f)
    return data

def check_config(data):
    # check that source and target directories exist
    if not os.path.isdir(data.source_path):
        logger.error('Cannot find source path')
        raise FileNotFoundError('Source path is invalid')
    if not os.path.isdir(data.target_path):
        logger.error('Cannot find target path')
        raise FileNotFoundError('Target path is invalid')
    
    # check that all expected .sqlite databases exist
    # first, check what style of naming is used
    if data.simple_db_names:
        for day in data.days:
            if not os.path.isfile(data.source_path  + str(day) + "days.sqlite"):
                logger.error('Cannot find .sqlite file for day ' + str(day))
                raise FileNotFoundError('Missing .sqlite source file')
            if not os.path.isfile(data.target_path  + str(day) + "days.sqlite"):
                logger.error('Cannot find .sqlite file for day ' + str(day))
                raise FileNotFoundError('Missing .sqlite target file')
    else:
        for db in custom_db_names:
            if not os.path.isfile(data.source_path + db + ".sqlite"):
                logger.error('Cannot find .sqlite file for ' + db)
                raise FileNotFoundError('Missing .sqlite source file')
            if not os.path.isfile(data.target_path + db + ".sqlite"):
                logger.error('Cannot find .sqlite file for ' + db)
                raise FileNotFoundError('Missing .sqlite target file')


def batch_transfer(source_path, target_path, dbs)
    for index, source_db in enumerate(dbs):
        if index > 0:
            # -1 means plugging 8 day results into 5 day db, and so on
            transfer_data(source_path + source_db, target_path + dbs[index-1])

if __name__ == "__main__":
    data = get_config()
    check_config(data)
    if data.simple_db_names:
        dbs = [day + "days.sqlite" for day in days]
    else:
        dbs = [db + ".sqlite" for db in dbs]
    batch_transfer(data.source_path, data.target_path, dbs)

# does not run anything through TEMOA