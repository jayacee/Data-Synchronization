import struct
class json_structs:
    default_save = {
    "directory":"",
    "files":[]
        }
    file_struct = {
        "file_path": "",
        "file_hash": "",
	"last_written":0,
        }

class connection_constants:
    initial_connection_message = b"\1"
    update_file = b"\2"
    create_file = b"\3"
    delete_file = b"\4"

    update_file_no_bdiff = b"\5"
    update_file_zip = b"\6"
    create_file_zip = b"\7"

    transaction_acknowledge = b"\8"

    
class connection_structs:
    def deserialize_message(message):
        read_index = 0
        function_byte = message[read_index]
        read_index += 1
        file_path_len = int.from_bytes(message[read_index:read_index+2])
        read_index += 2
        file_path = message[read_index:read_index+file_path_len]
        read_index += file_path_len
        bdiff_len = int.from_bytes(message[read_index:read_index+8])
        read_index += 8
        bdiff_data = message[read_index:read_index+bdiff_len]
        read_index += bdiff_len
        file_hash = message[read_index:]
        return function_byte,file_path,bdiff_data,file_hash

    def deserialize_encrypted_message(message):
        read_index = 0
        n_once = message[read_index:read_index+12]
        read_index += 12
        message_length = int.from_bytes(message[read_index:read_index+8])
        read_index += 8
        message = message[read_index:read_index+message_length]
        return n_once,message
    
    def make_encrypted_message(n_once,message):
        message_length = len(message).to_bytes(8,byteorder="big")
        return n_once+message_length+message
    def make_change_file_message(file_path,binary_diff_data,md5_digest,function_byte=connection_constants.update_file):
        file_path_len = len(file_path).to_bytes(2)
        binary_diff_data_len = len(binary_diff_data).to_bytes(8)
        return function_byte + file_path_len + file_path.encode() + binary_diff_data_len + binary_diff_data + md5_digest
        
    def make_connection_message():
        return initial_connection_message
    
