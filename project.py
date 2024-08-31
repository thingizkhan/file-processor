import os
import json
from socket import socket, AF_INET, SOCK_STREAM, timeout
import multiprocessing
import logging

ANNOUNCER_PORT = 5002
UPLOADER_PORT = 5001
LAN_ADDRESSES = ["192.168.2.156", "192.168.2.223,"]
TIMEOUT = 5
BUFFER_SIZE = 1024

class ChunkAnnouncer(multiprocessing.Process):
    def __init__(self, directory):
        super().__init__()
        self.directory = directory

    def run(self):
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.bind(('', ANNOUNCER_PORT))
            logging.info("ChunkAnnouncer started and bound to port %s", ANNOUNCER_PORT)
            while True:
                sock.listen(1)
                conn, addr = sock.accept()
                logging.info("Connection accepted from %s", addr)
                try:
                    file_list = os.listdir(self.directory)
                    data = {'files': file_list}
                    json_str = json.dumps(data)
                    conn.sendall(json_str.encode())
                    logging.info("Sent file list: %s", file_list)
                except Exception as e:
                    logging.error("Error occurred: %s", str(e))
                finally:
                    conn.close()
                    logging.info("Connection closed")

class ChunkDiscovery(multiprocessing.Process):
    def __init__(self):
        super().__init__()
        self.file_lists = multiprocessing.Manager().dict()

    def run(self):
        for address in LAN_ADDRESSES:
            with socket(AF_INET, SOCK_STREAM) as sock:
                sock.settimeout(TIMEOUT)
                try:
                    logging.info("Attempting to connect to address: %s", address)
                    sock.connect((address, ANNOUNCER_PORT))
                    data = sock.recv(1024)
                    file_list = json.loads(data.decode())
                    self.file_lists[address] = file_list['files']
                    logging.info("Received file list from %s: %s", address, file_list)
                except timeout:
                    logging.error("Connection to %s timed out", address)
                except Exception as e:
                    logging.error("An error occurred while connecting to %s: %s", address, str(e))

class ChunkDownloader(multiprocessing.Process):
    def __init__(self, filename, file_lists):
        super().__init__()
        self.filename = filename
        self.file_lists = file_lists

    def run(self):
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT)
            for address, file_list in self.file_lists.items():
                if self.filename in file_list:
                    try:
                        logging.info("Attempting to connect to address: %s", address)
                        sock.connect((address, UPLOADER_PORT))
                        sock.sendall(self.filename.encode())
                        logging.info("Request to download file: %s", self.filename)
                        with open(self.filename, 'wb') as file:
                            while True:
                                data = sock.recv(BUFFER_SIZE)
                                if not data:
                                    break
                                file.write(data)
                        logging.info("File downloaded successfully: %s", self.filename)
                        break
                    except timeout:
                        logging.error("Connection to %s timed out", address)
                    except Exception as e:
                        logging.error("An error occurred while downloading file from %s: %s", address, str(e))

class ChunkUploader(multiprocessing.Process):
    def __init__(self, directory):
        super().__init__()
        self.directory = directory

    def run(self):
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.bind(('', UPLOADER_PORT))
            logging.info("ChunkUploader started and bound to port %s", UPLOADER_PORT)
            while True:
                sock.listen(1)
                conn, addr = sock.accept()
                logging.info("Connection accepted from %s", addr)
                try:
                    filename = conn.recv(1024).decode()
                    filepath = os.path.join(self.directory, filename)
                    if os.path.exists(filepath):
                        logging.info("Start to upload file: %s", filename)
                        with open(filepath, 'rb') as file:
                            while True:
                                data = file.read(BUFFER_SIZE)
                                if not data:
                                    break
                                conn.sendall(data)
                        logging.info("File uploaded successfully: %s", filename)
                    else:
                        logging.warning("File not found: %s", filename)
                except Exception as e:
                    logging.error("Error occurred: %s", str(e))
                finally:
                    conn.close()
                    logging.info("Connection closed")

def main():
    logging.basicConfig(level=logging.INFO)

    directory = '/Users/durunef/Documents/canim/'
    filename = 'CMP.jpg'

    try:
        chunk_announcer = ChunkAnnouncer(directory)
        chunk_discovery = ChunkDiscovery()
        chunk_downloader = ChunkDownloader(filename, chunk_discovery.file_lists)
        chunk_uploader = ChunkUploader(directory)

        chunk_announcer.start()
        chunk_discovery.start()
        chunk_uploader.start()

        chunk_discovery.join()

        chunk_downloader.start()

        chunk_announcer.join()
        chunk_discovery.join()
        chunk_downloader.join()
        chunk_uploader.join()
    except Exception as e:
        logging.exception("An error occurred in main: %s", str(e))

if __name__ == "__main__":
    main()
