import os
import paramiko #type: ignore
import traceback
from ftplib import FTP
from app.logger import get_global_logger
# import pprint


def ftp_file_transfer(file_path, config):
    logger = get_global_logger()

    host = config["host"]
    username = config["username"]
    password = config["password"]
    output_path = config["file_path"]
    port = config["port"]  

    try:
        logger.info(f"Connecting to FTP host: {host}")
        # print(f"Connecting to FTP host: {host}")
        ftp = FTP()
        # ftp.set_pasv(True)
        ftp.connect(host,port,timeout=120)
        ftp.login(user=username, passwd=password)

        logger.info(f"Uploading {file_path} to {output_path}")
        with open(file_path, 'rb') as f:
            ftp.storbinary(f'STOR {output_path}', f)

        logger.info(f"Uploaded {file_path} as {output_path}")
        ftp.quit()

    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        logger.error(traceback.format_exc())


def sftp_file_transfer(file_path, config):
    logger = get_global_logger() 
    remote_dir = config["file_path"].replace("\\", "/")
    remote_file = f"{remote_dir}/{os.path.basename(file_path)}"
    try:
        logger.info(f"Attempting to connect..  {config["host"]}")
        transport = paramiko.Transport((config["host"], config.get("port", 22)))
        transport.connect(username=config["username"], password=config["password"])
        sftp = paramiko.SFTPClient.from_transport(transport)
        logger.info("Connection Successful !!")
        
    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        return 

    try:
        #ensure directory exists
        dirs = remote_dir.strip("/").split("/")
        path = ""
        for d in dirs:
            path += f"/{d}"
            try: sftp.listdir(path)
            except IOError: sftp.mkdir(path)

        sftp.put(file_path, remote_file)
        logger.info(f"Uploaded {file_path} → {remote_file}")
    finally:
        sftp.close()
        transport.close()