import socket
import time
import lib.structs as structs
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import lib.utils as utils

class connection_handler:
    def __init__(self,hostname,port,debugger,shared_key,mode="client"):
        self.mode = mode
        self.shared_key = base64.b64decode(shared_key)
        self.aes_object = AESGCM(self.shared_key)

        self.debugger = debugger
        self.hostname = hostname
        self.port = port
        if mode == "client":
            self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.threshold = 32
        self.timeout_time = 1
        
    def listen_for_connection(self):
        self.debugger.log_debug("[CONNECTION_HANDLER] Waiting for connection...")
        self.connection_object = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection_object.bind((self.hostname,self.port))
        self.connection_object.listen(1)
        self.connection_socket,client_address = self.connection_object.accept()
        self.debugger.log_msg(f"[CONNECTION_HANDLER] Connection from '{client_address}'")
        
    def make_connection(self):
        self.debugger.log_debug(f"[CONNECTION_HANDLER] Making connection to '{self.hostname}:{self.port}'")
        try:
            self.connection_socket.connect((self.hostname,self.port))
            self.debugger.log_debug("[CONNECTION_HANDLER] Successfully connected!")
            return True
        except ConnectionRefusedError:
            self.debugger.log_debug("[CONNECTION_HANDLER] Error! Connection refused")
            return False
        except TimeoutError:
            self.debugger.log_debug("[CONNECTION_HANDLER] Error! Connection timed out")
            return False
        except Exception as unhandled_error:
            self.debugger.log_debug(f"[CONNECTION_HANDLER] Error! {unhandled_error}")
            return False

    def read_in_chunks(self,chunk_size=4096):
        chunks = b""
        timeout = 0
        while True:
            try:
                if timeout >= self.threshold:
                    self.debugger.log_msg(f"[CONNECTION_HANDLER] Failed to read data after {self.threshold} attempts")
                    return False
                chunk = self.connection_socket.recv(chunk_size)
                chunks += chunk
                if not chunk or len(chunk) < chunk_size:
                    break
            except ConnectionResetError:
                self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.debugger.log_msg("[CONNECTION_HANDLER] Error! Connection reset when reading data!")
                timeout += 1
                self.reconnect()
            except socket.timeout:
                self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.debugger.log_msg("[CONNECTION_HANDLER] Error! Connection timed out when reading data!")
                timeout += 1
                self.reconnect()
            except Exception as socket_error:
                self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.debugger.log_msg(f"[CONNECTION_HANDLER] Error when reading! {socket_error}")
                timeout += 1
                self.reconnect()
        return chunks

    # sends data in chunks and saves the number of bytes sent in a variable
    # much more resilient than trying to send it all at one time, since if a connection is interrupted it would need to be restarted
    def send_in_chunks(self,data,chunk_size=4096):
        chunk_index = 0
        timeout = 0
        while True:
            try:
                if timeout >= self.threshold:
                    self.debugger.log_msg(f"[CONNECTION_HANDLER] Failed to send data after {self.threshold} attempts")
                    return False
                self.connection_socket.send(data[chunk_index:chunk_index+chunk_size])
                # only updates chunk_index after data is successfully sent
                chunk_index += chunk_size
                if chunk_index >= len(data):
                    break
            except ConnectionResetError:
                self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.debugger.log_msg("[CONNECTION_HANDLER] Error! Connection reset when sending data!")
                timeout += 1
                self.reconnect()
            except socket.timeout:
                self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.debugger.log_msg("[CONNECTION_HANDLER] Error! Connection timed out when sending data!")
                timeout += 1
                self.reconnect()
            except Exception as socket_error:
                self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.debugger.log_msg(f"[CONNECTION_HANDLER] Error when sending! {socket_error}")
                timeout += 1
                self.reconnect()
    def reconnect(self):
        if self.mode == "client":
            self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.make_connection()
        elif self.mode == "server":
            self.listen_for_connection()
            
    def read_data(self):
        encrypted_message = self.read_in_chunks()
        #encrypted_message = utils.decompress_bytes(zipped_message)
        n_once,encrypted_message = structs.connection_structs.deserialize_encrypted_message(encrypted_message)
        return self.aes_object.decrypt(n_once,encrypted_message,associated_data=None)
    def send_data(self,data):
        n_once = os.urandom(12)
        encrypted_message = self.aes_object.encrypt(n_once,data,associated_data=None)
        encrypted_formatted_message = structs.connection_structs.make_encrypted_message(n_once,encrypted_message)
        timeout = 0
        # keeps retrying sending data for self.threshold times
        self.send_in_chunks(encrypted_formatted_message)
        return True
                
                
        
