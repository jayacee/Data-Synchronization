import socket
import lib.debug
import base64
import lib.utils as utils
import lib.structs as structs
import lib.cryptohelper as cryptohelper
import lib.connection_handler as connection_handler
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import bsdiff4
import pathlib
import configparser
import glob
import os

class server:
    def log_function_message(self,function_byte,file_path,bdiff_data):
        self.debugger.log_debug(f'''Received Message:
Function Byte: {hex(function_byte)}
File Path: {file_path}
BDIFF Data Length: {len(bdiff_data)}\n''')

    def do_initial_connection(self):
        current_file_data = ""
        current_files = glob.glob(f"{self.server_folder}/*",recursive=True)
        current_file_data = ""
        for file in current_files:
            file_hash = cryptohelper.calculate_hash_from_file(file)
            current_file_data += f"{file}:{file_hash},"
            
        current_file_data = structs.connection_constants.initial_connection_message + current_file_data.encode()

        self.connection_handler.send_data(current_file_data)

    def verify_file_integrity(self,file_patched,file_hash):
        calc_hash = cryptohelper.calculate_md5_digest_from_bytes(file_patched)
        if calc_hash != file_hash:
            self.debugger.log_msg(f"[SERVER] File integrity check failed! expected {bdiff_hash} and got {calc_hash}")
            return False
        else:
            self.debugger.log_debug(f"[SERVER] File integrity check succeeded!")
            return True
        
    def handle_file_update(self,file_path,bdiff_data,file_hash):
        file_handle = open(file_path,'rb')
        file_content = file_handle.read()
        file_handle.close()

        file_patched = bsdiff4.patch(file_content,bdiff_data)
        if not self.verify_file_integrity(file_patched,file_hash):
            exit(1)
            
        file_handle = open(file_path,'wb')
        file_handle.write(file_patched)
        file_handle.close()
        
        self.debugger.log_debug(f"[SERVER] Patched file {file_path}")

    def handle_file_create(self,file_path,bdiff_data,file_hash):
        if not self.verify_file_integrity(bdiff_data,file_hash):
            exit(1)
            
        file_handle = open(file_path,'wb')
        file_handle.write(bdiff_data)
        file_handle.close()
    def handle_file_create_zip(self,file_path,bdiff_data,file_hash):
        decompressed_bytes = uils.decompress_bytes(bdiff_data)
        self.handle_file_create(file_path,decompressed_bytes,file_hash)

    def handle_file_delete(self,file_path):
        os.remove(file_path)

    def handle_update_file_no_bdiff(self,file_path,bdiff_data,file_hash):
        if not self.verify_file_integrity(bdiff_data,file_hash):
            exit(1)
        file_handle = open(file_path,'wb')
        file_handle.write(bdiff_data)
        file_handle.close()

    def handle_update_file_zip(self,file_path,bdiff_data,file_hash):
        decompressed_bytes = uils.decompress_bytes(bdiff_data)
        self.handle_update_file_no_bdiff(file_path,decompressed_bytes,file_hash)
    
    def __init__(self):
        self.debugger = lib.debug.debugger(is_verbose=True)
        config = configparser.ConfigParser()
        config.read("config.ini")
        
        self.shared_key = config["connection"]["shared_key"]
        self.server = config["connection"]["server"]
        self.port = int(config["connection"]["port"])
        self.server_folder = config["general"]["server_replicated_folder"]

        self.connection_handler = connection_handler.connection_handler(self.server,self.port,self.debugger,self.shared_key,mode="server")

        self.connection_handler.listen_for_connection()
        self.do_initial_connection()

        while True:
            data = self.connection_handler.read_data()
            function_byte,file_path,bdiff_data,file_hash = structs.connection_structs.deserialize_message(data)
            self.log_function_message(function_byte,file_path,bdiff_data)
            function_byte = int.to_bytes(function_byte)
            file_path = file_path.decode()
            file_path = pathlib.PurePath(file_path).relative_to(file_path.split("\\")[0])
            file_path = os.path.join(self.server_folder,file_path)
            
            if function_byte == structs.connection_constants.update_file:
                self.debugger.log_msg(f"[SERVER] Updating file {file_path}...")
                self.handle_file_update(file_path,bdiff_data,file_hash)

            elif function_byte == structs.connection_constants.update_file_no_bdiff:
                self.debugger.log_msg(f"[SERVER] Updating file {file_path} without patching...")
                self.handle_update_file_no_bdiff(file_path,bdiff_data,file_hash)

            elif function_byte == structs.connection_constants.update_file_zip:
                self.debugger.log_msg(f"[SERVER] Updating file {file_path} with zip...")
                self.handle_update_file_zip(file_path,bdiff_data,file_hash)
                
            elif function_byte == structs.connection_constants.create_file:
                self.debugger.log_msg(f"[SERVER] Adding file {file_path}...")
                self.handle_file_create(file_path,bdiff_data,file_hash)

            elif function_byte == structs.connection_constants.create_file:
                self.debugger.log_msg(f"[SERVER] Adding file {file_path} with zip...")
                self.handle_file_create_zip(file_path,bdiff_data,file_hash)
                
            elif function_byte == structs.connection_constants.delete_file:
                self.debugger.log_msg(f"[SERVER] Deleting file {file_path}...")
                self.handle_file_delete(file_path)

            self.connection_handler.send_data(structs.connection_constants.transaction_acknowledge)
            

_server = server()
