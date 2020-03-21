import logging
import subprocess
import os
import time
import threading
from lib.database import Database


logger = logging.getLogger()

class Encryption:
    def __init__(self, config, database, tapelibrary, tools, local=False):
        self.config = config
        self.database = database
        self.tapelibrary = tapelibrary
        self.tools = tools
        self.local_files = local
        self.interrupted = False
        self.active_threads = []

    def set_interrupted(self):
        self.interrupted = True

    def encrypt_single_file_thread(self, threadnr, id, filepath, filename_enc):
        thread_db = Database(self.config)

        thread_db.update_filename_enc(filename_enc, id)

        time_started = time.time()

        if not self.local_files:
            command = ['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-iter', '100000', '-in',
                       os.path.abspath('{}/{}'.format(self.config['local-data-dir'], filepath)), '-out',
                       os.path.abspath('{}/{}'.format(self.config['local-enc-dir'], filename_enc)), '-k',
                       self.config['enc-key']]
        else:
            command = ['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-iter', '100000', '-in',
                       os.path.abspath('{}/{}'.format(self.config['local-base-dir'], filepath)), '-out',
                       os.path.abspath('{}/{}'.format(self.config['local-enc-dir'], filename_enc)), '-k',
                       self.config['enc-key']]
        openssl = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   preexec_fn=os.setpgrp)

        if len(openssl.stderr.readlines()) == 0:
            logger.debug(
                "Execution Time: Encrypt file with openssl: {} seconds".format(time.time() - time_started))

            time_started = time.time()
            md5 = self.tools.md5sum(os.path.abspath("{}/{}".format(self.config['local-enc-dir'], filename_enc)))
            logger.debug("Execution Time: md5sum encrypted file: {} seconds".format(time.time() - time_started))

            filesize = os.path.getsize(os.path.abspath('{}/{}'.format(self.config['local-enc-dir'], filename_enc)))
            encrypted_date = int(time.time())
            thread_db.update_file_after_encrypt(filesize, encrypted_date, md5, id)

            if not self.local_files:
                time_started = time.time()
                os.remove(os.path.abspath("{}/{}".format(self.config['local-data-dir'], filepath)))
                logger.debug("Execution Time: Remove file after encryption: {} seconds".format(
                    time.time() - time_started))
        else:
            logger.warning("encrypt file failed, file: {} error: {}".format(id, openssl.stderr.readlines()))
            logger.debug(
                "Execution Time: Encrypt file with openssl: {} seconds".format(time.time() - time_started))

        self.active_threads.remove(threadnr)


    def encrypt(self):
        logger.info("Starting encrypt files job")

        while True:
            files = self.database.get_files_to_be_encrypted()

            if len(files) == 0:
                break

            for file in files:
                for i in range(0, self.config['threads']):
                    if i not in self.active_threads:
                        next_thread = i
                        break

                logger.info("Starting Thread #{}, processing: id: {}, filename: {}".format(next_thread, file[0], file[1]))

                filename_enc = self.tools.create_filename_encrypted()
                while self.database.filename_encrypted_already_used(filename_enc):
                    logger.warning("Filename ({}) encrypted already exists, creating new one!".format(filename_enc))
                    filename_enc = self.tools.create_filename_encrypted()

                self.active_threads.append(next_thread)
                x = threading.Thread(target=self.encrypt_single_file_thread,
                                     args=(next_thread, file[0], file[2], filename_enc,),
                                     daemon=True)
                x.start()

                while threading.active_count() > self.config['threads']:
                    time.sleep(10)

                if self.interrupted:
                    while threading.active_count() > 1:
                        time.sleep(1)
                    break

            if self.interrupted:
                while threading.active_count() > 1:
                    time.sleep(1)
                break

        ## encrypt
        # openssl enc -aes-256-cbc -pbkdf2 -iter 100000 -in 'videofile.mp4' -out test.enc -k supersicherespasswort
        ## decrypt
        # openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 -in test.enc -out test.mp4

    def restore():
        ## TODO: Restore file by given name, path or encrypted name
        pass