import tomllib
import os
import logging

from opt_gap_check import transfer_data

logger = logging.getLogger(__name__)


def get_config():
    with open("opt_gap_config.toml", "rb") as f:
        data = tomllib.load(f)
    return data

def check_config(data):
    # check that source and target directories exist
    if not os.path.isdir(data.get("source_path")):
        logger.error('Cannot find source path')
        raise FileNotFoundError('Source path is invalid')
    if not os.path.isdir(data.get("target_path")):
        logger.error('Cannot find target path')
        raise FileNotFoundError('Target path is invalid')
    
    # check that all expected .sqlite databases exist
    # first, check what style of naming is used
    if data["simple_db_names"]:
        for day in data.get("days"):
            if not os.path.isfile(data.get("source_path")  + str(day) + "_periods.sqlite"):
                logger.error('Cannot find .sqlite file for day ' + str(day))
                raise FileNotFoundError('Missing .sqlite source file')
            if not os.path.isfile(data.get("target_path")  + str(day) + "_periods.sqlite"):
                logger.error('Cannot find .sqlite file for day ' + str(day))
                raise FileNotFoundError('Missing .sqlite target file')
    else:
        for db in data.get("custom_db_names"):
            if not os.path.isfile(data.get("source_path") + db + ".sqlite"):
                logger.error('Cannot find .sqlite file for ' + db)
                raise FileNotFoundError('Missing .sqlite source file')
            if not os.path.isfile(data.get("target_path") + db + ".sqlite"):
                logger.error('Cannot find .sqlite file for ' + db)
                raise FileNotFoundError('Missing .sqlite target file')


def batch_transfer(source_path, target_path, direction, dbs):
    num_dbs = len(dbs)
    for index, source_db in enumerate(dbs):
        if direction == -1:
            if index > 0:
                # -1 means plugging 8 day results into 5 day db, and so on
                transfer_data(source_path + source_db, target_path + dbs[index-1])
                logger.info('Transferred successfully from ' + source_db + ' to ' + target_path + dbs[index-1])
        if direction == 1:
            if index < len(dbs) - 1:
                # 1 means plugging lower number periods into higher number
                transfer_data(source_path + source_db, target_path + dbs[index+1]) 
                logger.info('Transferred successfully from ' + source_db + ' to ' + target_path + dbs[index+1])

if __name__ == "__main__":
    data = get_config()
    check_config(data)
    if data["simple_db_names"]:
        dbs = [str(day) + "_periods.sqlite" for day in data.get("days")]
    else:
        dbs = [db + ".sqlite" for db in data.get("custom_db_names")]
    batch_transfer(data.get("source_path"), data.get("target_path"), data.get("direction"),dbs)

# does not run anything through TEMOA