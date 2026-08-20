import hashlib

def calculate_hash_from_bytes(target_bytes):
    return hashlib.sha256(target_bytes).hexdigest()

def calculate_hash_from_file(target_file):
    file_handle = open(target_file,'rb')
    file_data = file_handle.read()
    file_handle.close()
    return calculate_hash_from_bytes(file_data)

def calculate_md5_digest_from_bytes(target_bytes):
    return hashlib.md5(target_bytes).digest()

def calculate_md5_digest_from_file(target_file):
    file_handle = open(target_file,'rb')
    file_data = file_handle.read()
    file_handle.close()
    return calculate_md5_digest_from_bytes(file_data)
