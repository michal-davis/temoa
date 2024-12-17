import sys
import os
import csv
import logging


logger = logging.getLogger(__name__)

from opt_gap_check import transfer_data


def parse_target_file(targets_file):
	# returns a list of dicts
	with open(targets_file) as csvfile:
		reader = csv.DictReader(csvfile)
		targets = []
		for row in reader:
			if os.path.isfile(row['source_file']) and os.path.isfile(row['target_file']):
				# both files exist, can add to targets
				logger.info("{row['source_file']} and {row['target_file']} both exist")
				targets.append(row)
			else:
				logger.warn("Cannot find {row['source_file']} and/or {row['target_file']}")
	return targets

def setup_opt_gap_with_targets(targets):
	for target in targets:
		transfer_data(target['source_file'],target['target_file'])
		logger.info("Transferred successfully from {row['source_file']} to {row['target_file']}")

if __name__=="__main__":
	if len(sys.argv) >= 2: targets_file = sys.argv[1]
	if not os.path.isfile(targets_file):
		print(f"{targets_file} does not exist")
		sys.exit(1)
	targets = parse_target_file(targets_file)
	if len(targets) >=1: setup_opt_gap_with_targets(targets)
	print("Finished transferring!")