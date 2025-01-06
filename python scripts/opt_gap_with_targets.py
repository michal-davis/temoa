import sys
import os
import csv
import logging
import shutil

from opt_gap_check import transfer_data

# when run in terminal, accepts up to three arguments:
# 1) path to a target file in csv format
# 2) mode (default = simple)
# 3) path prefix (optional)
# Mode may be 'simple' or 'cross' (abbreviation 's' and 'c' also ok). Default is simple
# If simple, 
# 	target file must have columns source_file and target_file
# If cross,
# 	target file must have columns source_file, target_data, save_as

# if a path prefix is provided, 
# the target file and the databases it points to will be searched for in the location given by the path prefix

logger = logging.getLogger(__name__)
SIMPLE = 's'
CROSS = 'c'

def parse_mode(input):
	if input.casefold() == 'cross' or input.casefold() == CROSS:
		return CROSS
	elif input.casefold() == 'simple' or input.casefold() == SIMPLE:
		return SIMPLE
	else:
		print(f"{input} is not a valid mode, assuming simple")
		return SIMPLE
		
def parse_target_file(file, mode, path_prefix=''):
	if mode == SIMPLE:
		return parse_simple_target_file(file,path_prefix)
	if mode == CROSS:
		return prepare_cross_targets(file,path_prefix)

def parse_simple_target_file(targets_file, path_prefix=''):
	# returns a list of dicts
	with open(targets_file, newline='') as csvfile:
		reader = csv.DictReader(csvfile)
		targets = []
		for row in reader:
			p_row =  {'source_file': os.path.join(path_prefix,row['source_file']), 'target_file': os.path.join(path_prefix,row['target_file'])}
			if os.path.isfile(p_row['source_file']) and os.path.isfile(p_row['target_file']):
				# both files exist, can add to targets
				logger.info("{p_row['source_file']} and {p_row['target_file']} both exist")
				targets.append(p_row)
			else:
				logger.warning(f"Cannot find {p_row['source_file']} and/or {p_row['target_file']}")
	return targets

def prepare_cross_targets(targets_file, path_prefix=''):
	# returns a list of dicts, and creates needed files
	with open(targets_file, newline='') as csvfile:
		reader = csv.DictReader(csvfile)
		targets = []
		for row in reader:
			# confirm source_file and target_data both exist
			if os.path.isfile(os.path.join(path_prefix,row['source_file'])) and os.path.isfile(os.path.join(path_prefix,row['target_data'])):

				logger.info("{row['source_file']} and {row['target_data']} both exist")
				
				# copy target data to file named [save_as]
				shutil.copyfile(os.path.join(path_prefix,row['target_data']), os.path.join(path_prefix,row['save_as']))
				
				# create version of row in source_file, target_file form
				to_add = {'source_file': os.path.join(path_prefix,row['source_file']), 'target_file': os.path.join(path_prefix,row['save_as'])}
				targets.append(to_add)
			else:
				logger.warning(f"Cannot find {row['source_file']} and/or {row['target_data']}")
	return targets

def setup_opt_gap_with_targets(targets):
	for target in targets:
		transfer_data(target['source_file'],target['target_file'])
		logger.info("Transferred successfully from {row['source_file']} to {row['target_file']}")

	
if __name__=="__main__":
	# Get and check target file
	if len(sys.argv) >= 2: targets_file = sys.argv[1]
	
	if len(sys.argv) >=4: 
		path_prefix = sys.argv[3]
		targets_file = os.path.join(path_prefix, targets_file)
	else:
		path_prefix = ''

	if not os.path.isfile(targets_file):
		print(f"{targets_file} does not exist")
		sys.exit(1)
	
	# Get and check mode
	if len(sys.argv) >= 3: 
		mode = parse_mode(sys.argv[2])
	else:
		mode = SIMPLE


	targets = parse_target_file(targets_file, mode, path_prefix)
	if len(targets) >=1: setup_opt_gap_with_targets(targets)
	print("Finished transferring!")


