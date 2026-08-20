import socket
import zipfile
import io
def compress_bytes(bytes_to_compress):
        zip_buffer = io.BytesIO()
        
        zip_file = zipfile.ZipFile(zip_buffer,"w",compression=zipfile.ZIP_LZMA)
        zip_file.writestr("A",bytes_to_compress) # file name could be anything
        zip_file.close()

        return zip_buffer.getvalue()

def decompress_bytes(bytes_to_decompress):
        zip_file = zipfile.ZipFile(io.BytesIO(bytes_to_decompress))
        ret_bytes = zip_file.read("A")
        zip_file.close()
        return ret_bytes
        
        

