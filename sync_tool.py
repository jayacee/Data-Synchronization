import os
import configparser
import json
import argparse
import glob
import pathlib
from datetime import datetime
import time
import bsdiff4
import shutil

import lib.structs as sync_structs
import lib.cryptohelper as cryptohelper
import lib.debug as debug
import lib.connection_handler as connection_handler
import lib.utils as utils

class sync_tool:
    def __init__(self,directory=None,is_verbose=False):
        self.debugger = debug.debugger(is_verbose=is_verbose)
        self.debugger.log_debug(f"[MAIN] Beginning program at {datetime.now()}")

        # directory chosen for replication
        self.directory = directory

        # reads the "config.ini" file for certain values
        self.read_ini()

        # if the user chose a directory we must perform a first time set up
        if directory != None:
            self.debugger.log_debug(f"[MAIN] Running new setup for directory '{directory}'")
            self.make_new_save_file(directory)
            self.debugger.log_debug("[MAIN] Successfully made new save file")
            self.cache_directory(directory)
            self.debugger.log_debug("[MAIN] Successfully cached all directories")

        # reads the save file chosen in the config.ini file
        # stores file names and hashes so a quick reload can be performed if the directory isn't chosen next run
        save_file_data = self.read_save_file()
        self.parse_save_file(save_file_data)
        
        # makes a connection handler and attempts to connect to the server chosen in the config.ini file
        self.connection_handler = connection_handler.connection_handler(self.server,self.port,self.debugger,self.shared_key)
        connection_success = self.connection_handler.make_connection()

        if not connection_success:
            self.debugger.log_msg(f"[MAIN] Failed to connect to '{self.server}:{self.port}'")
            exit(1)

        self.do_initial_connection()
        self.main_monitor_loop()

    def get_file_last_modified(self,file_name):
        file_path = pathlib.Path(file_name)
        return file_path.stat().st_mtime
        
    def read_ini(self):
        self.debugger.log_debug("[MAIN] Reading config.ini")
        config = configparser.ConfigParser()
        config.read("config.ini")
        self.save_file_name = config["general"]["save_file"]
        # the cycle speed is how often (in seconds) the directory should be checked for changes
        self.cycle_speed = float(config["general"]["cycle_speed"])
        
        self.shared_key = config["connection"]["shared_key"]
        self.server = config["connection"]["server"]
        self.port = int(config["connection"]["port"])
        
    def save_file_exists(self):
        return os.path.exists(self.save_file_name)
    
    def read_save_file(self):
        data_file = open(self.save_file_name)
        save_file_data = json.load(data_file)
        data_file.close()
        return save_file_data
    
    def parse_save_file(self,save_file_data):
        self.directory = save_file_data["directory"]
        self.files = save_file_data["files"]
        self.file_names = []
        for file_single in self.files:
            self.file_names.append(file_single["file_path"])

    def output_save_file(self,save_file_data):
        file_handle = open(self.save_file_name,'w')
        json.dump(save_file_data,file_handle)
        file_handle.close()

    def get_all_monitor_files(self):
        return glob.glob(f"{self.directory}/*",recursive=True)

    def make_new_save_file(self,directory):
        file_list = self.get_all_monitor_files()
        file_obj_list = []
        for file_single in file_list:
            self.debugger.log_debug(f"[MAIN] adding entry for {file_single}")
            new_file_obj = sync_structs.json_structs.file_struct.copy()
            
            new_file_obj["file_path"] = file_single
            
            # use SHA256 hexdigest at rest but MD5 digest in transport to save bandwidth, since MD5 takes up half the number of bytes
            file_hash = cryptohelper.calculate_hash_from_file(file_single)
            new_file_obj["file_hash"] = file_hash

            new_file_obj["last_written"] = self.get_file_last_modified(file_single)
            
            file_obj_list.append(new_file_obj)
            
        save_obj = sync_structs.json_structs.default_save
        save_obj["directory"] = directory
        save_obj["files"] = file_obj_list

        self.output_save_file(save_obj)

    def does_cached_exist(self,file_name):
        return os.path.exists(f"cached/{file_name}")

    def cache_file_single(self,file_name):
        # cache files in the "cached/" directory so we can calculate the BDIFF if the original file is changed
        # copy doesnt preserve file stats like copy2, since the cached file stats aren't important
        shutil.copy(file_name,f"cached/{file_name}")

    def cache_directory(self,directory_name):
        if os.path.exists("cached"):
            shutil.rmtree("cached")
        shutil.copytree(directory_name,f"cached/{directory_name}")

    def get_diff_bytes(self,file1,file2):
        self.debugger.log_debug(f"[MAIN] Calculating binary difference between files '{file1}' and '{file2}'")
        file1_handle = open(file1,'rb')
        file2_handle = open(file2,'rb')

        file1_bytes = file1_handle.read()
        file2_bytes = file2_handle.read()

        file1_handle.close()
        file2_handle.close()
        
        # bsdiff4 is an extremely compact patching algorithm
        return bsdiff4.diff(file1_bytes,file2_bytes)

    def update_file(self,file_object):
        file_name = file_object["file_path"]
        self.debugger.log_debug(f"[MAIN] File '{file_name}' has been modified, updating...")

        # finds the numerical index of the file we need to update n self.files
        file_index = self.files.index(file_object)

        # updates the file object in memory
        self.files[file_index]["last_written"] = self.get_file_last_modified(file_name)
        self.files[file_index]["file_hash"] = cryptohelper.calculate_hash_from_file(file_name)

        #  the actual self.files structure contains the "files" and "directory" arrays, so we need to clone the original and update those
        save_file_obj = sync_structs.json_structs.default_save.copy()
        save_file_obj["files"] = self.files
        save_file_obj["directory"] = self.directory
        
        self.output_save_file(save_file_obj)
        self.cache_file_single(file_name)

    def get_file_content(self,file_path):
        file_handle = open(file_path,'rb')
        file_content = file_handle.read()
        file_handle.close()
        return file_content
        
    def get_file_length(self,file_path):
        return len(self.get_file_content(file_path))

    def handle_file_modification(self,file_object):
        file_name = file_object["file_path"]

        file_content = self.get_file_content(file_name)
        file_length = len(file_content)
        cached_diff = self.get_diff_bytes(f"cached/{file_name}",file_name)
        
        self.update_file(file_object)
        # md5 in transit
        file_hash = cryptohelper.calculate_md5_digest_from_file(file_name)

        compressed_data = utils.compress_bytes(file_content)
        compressed_len = len(compressed_data)
        if compressed_len < file_length and compressed_len < len(cached_diff):
            file_change_message = sync_structs.connection_structs.make_change_file_message(file_name,compressed_data,file_hash,function_byte=sync_structs.connection_constants.update_file_zip)
        # if the patch for the file is larger than the file's contents, send the file rather than the patch
        elif file_length <= len(cached_diff):
            file_change_message = sync_structs.connection_structs.make_change_file_message(file_name,file_content,file_hash,function_byte=sync_structs.connection_constants.update_file_no_bdiff)
        else:
            file_change_message = sync_structs.connection_structs.make_change_file_message(file_name,cached_diff,file_hash)
        self.connection_handler.send_data(file_change_message)

    
    def handle_new_file(self,file_path):
        self.debugger.log_debug(f"[MAIN] File '{file_path}' added, updating...")
        self.cache_file_single(file_path)
        file_struct = sync_structs.json_structs.file_struct.copy()
        file_struct["file_path"] = file_path
        file_struct["file_hash"] = cryptohelper.calculate_hash_from_file(file_path)
        file_struct["last_written"] = self.get_file_last_modified(file_path)
        
        self.file_names.append(file_path)
        self.files.append(file_struct)

        save_file_obj = sync_structs.json_structs.default_save.copy()
        save_file_obj["files"] = self.files
        save_file_obj["directory"] = self.directory
        
        self.output_save_file(save_file_obj)

        self.add_file_single(file_path)

    def add_file_single(self,file_name):
        file_handle = open(file_name,'rb')
        file_data = file_handle.read()
        file_handle.close()

        file_data_compressed = utils.compress_bytes(file_data)
        file_hash = cryptohelper.calculate_md5_digest_from_bytes(file_data)
        
        if len(file_data_compressed) < len(file_data):
            file_add_message = sync_structs.connection_structs.make_change_file_message(file_name,file_data,file_hash,function_byte=sync_structs.connection_constants.create_file_zip)
        else:
            file_add_message = sync_structs.connection_structs.make_change_file_message(file_name,file_data,file_hash,function_byte=sync_structs.connection_constants.create_file)
        self.connection_handler.send_data(file_add_message)
        
    def delete_file_single(self,file_name):
        file_del_message = sync_structs.connection_structs.make_change_file_message(file_name,b"",function_byte=sync_structs.connection_constants.delete_file)
        self.connection_handler.send_data(file_del_message)
        
    def add_all_files(self):
        # for a first time synchronization, we send all the files over
        for file in self.files:
            file_path = file["file_path"]
            file_hash = file["file_hash"]
            self.add_file_single(file_path)
            
    def check_if_relative_file_exists(self,relative_path_name):
        # checks if a server file exists on the client, taking into account the difference in directory names
        full_path_name = os.path.join(self.directory,relative_path_name)        
        return full_path_name in self.file_names
    
    def do_initial_connection(self):
        # as defined in structs.py, the intial_connection message starts with a structs.connection_constants.initial_connection_message byte
        initial_connection_bytes = self.connection_handler.read_data()
        if int.to_bytes(initial_connection_bytes[0]) != sync_structs.connection_constants.initial_connection_message:
            self.debugger.log_msg(f"[MAIN] Error! Incorrect initial_connection_message identifier : {initial_connection_bytes[0]}")
            exit(1)

        # removes the initial connection byte
        initial_connection_bytes = initial_connection_bytes[1:]
        
        decoded_data = initial_connection_bytes.decode()
        if decoded_data == "":
            self.add_all_files()
        else:
            file_chunks = decoded_data.split(",")
            # for each file the server sends over, it is contained in a file_name:sha256_hash pair, with each file chunk being delimeted by a ","
            for file_chunk in file_chunks:
                file_delim = file_chunk.split(":")
                file_name = file_delim[0]
                if file_name == "":
                    # server tacks on a ":" at the end of the connection data, so ignore the last entry if it is ""
                    continue
                # removes the root directory of the file the server sends over so we can compare the file names rather than the paths
                relative_file_path = pathlib.PurePath(file_name).relative_to(file_name.split("\\")[0])
                
                if not self.check_if_relative_file_exists(relative_file_path):
                    self.delete_file_single(file_name)
                file_hash = file_delim[1]
        
    def handle_deleted_file(self,file_object):
        file_name = file_object["file_path"]
        self.debugger.log_debug(f"[MAIN] File '{file_name}' deleted, updating...")
        self.files.remove(file_object)

        save_file_obj = sync_structs.json_structs.default_save.copy()
        save_file_obj["files"] = self.files
        save_file_obj["directory"] = self.directory
        
        os.remove(f"cached/{file_name}")
        self.output_save_file(save_file_obj)

        file_add_message = sync_structs.connection_structs.make_change_file_message(file_name,b"",b"",function_byte=sync_structs.connection_constants.delete_file)
        self.connection_handler.send_data(file_add_message)
        
    def main_monitor_loop(self):
        self.debugger.log_msg("[MAIN] Monitoring files...")
        while True:
            for monitor_file in self.files:
                save_file_name = monitor_file["file_path"]
                if not os.path.exists(save_file_name):
                    self.debugger.log_msg(f"[MAIN] File '{save_file_name}' deleted")
                    self.handle_deleted_file(monitor_file)
                    
                    # waits for the transaction_acknowledge_byte to prevent race condition
                    self.connection_handler.read_data()
                elif self.get_file_last_modified(save_file_name) > monitor_file["last_written"]:
                    self.debugger.log_msg(f"[MAIN] File '{save_file_name}' modified")
                    self.handle_file_modification(monitor_file)
                    
                    # waits for the transaction_acknowledge_byte to prevent race condition
                    self.connection_handler.read_data()
                     
            for file_single in self.get_all_monitor_files():
                # checks if a file has been created
                if file_single not in self.file_names:
                    self.debugger.log_msg(f"[MAIN] File '{file_single}' added")
                    self.handle_new_file(file_single)
                    
                    # waits for the transaction_acknowledge_byte to prevent race condition
                    self.connection_handler.read_data()
            time.sleep(self.cycle_speed)
        
 
def main():
    parser = argparse.ArgumentParser(description="SyncTool CLI")

    parser.add_argument("-d","--directory",type=str,help="The directory to monitor. Leave blank to resume from save file",default=None)
    parser.add_argument("-v","--verbose",action="store_true",help="Enable verbose debugging")

    cli_args = parser.parse_args()

    sync_tool_obj = sync_tool(directory=cli_args.directory,is_verbose=cli_args.verbose)
    
if __name__ == "__main__":
    main()
    
