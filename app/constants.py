import os
import json

from app.utils import Helper

utils = Helper()

root_dir = os.path.dirname(os.path.dirname(__file__))
conf_path = os.path.join(root_dir, "config", "config.json")
path_root = os.path.join(root_dir,"paths.json")

CONFIG = utils.load_json(conf_path)
PATHS =  utils.load_json(path_root)

# -----------------------
# ENSURE DIRS
# -----------------------

out_dir = os.path.join(root_dir,"output")
OUTPUT_DIR = PATHS.get("output_path", out_dir)

in_dir = os.path.join(root_dir,"input")
INPUT_DIR = PATHS.get("input_path",in_dir)

LOG_DIR = os.path.join(OUTPUT_DIR,"logs")
DATA_DIR = os.path.join(OUTPUT_DIR,"data")

def ensure_dirs():
    for d in [INPUT_DIR, OUTPUT_DIR, LOG_DIR, DATA_DIR]:
        utils.create_dir(d)

def conf_schl():
    pth = utils.load_json(path_root)
    return pth["CONFIG_SCH"]

def conf_db():
    pth = utils.load_json(path_root)
    return pth["CONFIG_DB"] 

def conf_ftp():
    pth = utils.load_json(path_root)
    return pth["CONFIG_FTP"]

def conf_sp():
    pth = utils.load_json(path_root)
    return pth["CONFIG_SP"] 

#Bin size to bin data
BIN_SIZE = 60
FILL_NA = "Nil"
