import logging
import sys

from tapebackup.lib import database
from functions.encryption import Encryption
from tapebackup.lib import Tools

logger = logging.getLogger()


class Restore:
    def __init__(self, config, engine, tapelibrary, tools, local=False):
        self.config = config
        self.session = database.create_session(engine)
        self.tapelibrary = tapelibrary
        self.tools = tools
        self.local_files = local
        self.interrupted = False
        self.encryption = Encryption(config, database, tapelibrary, tools, local)
        self.active_threads = []
        self.jobid = None

    def set_interrupted(self):
        self.interrupted = True

    def start(self, files, tape=None, filelist=""):
        ## TODO: Restore file by given name, path or encrypted name
        if files is None:
            files = []
        files = Tools.wildcard_to_sql_many(files)
        if filelist:
            files += self.read_filelist(filelist)

        file_ids = self.resolve_file_ids(files, tape)
        if not file_ids:
            logger.error("None of the specified files found")
            return

        self.jobid = database.add_restore_job(self.session)
        database.add_restore_job_files(self.session, self.jobid, file_ids)

        print(f"Restore job {self.jobid} created:")
        self.status()
        self.cont()

    table_format_next_tapes = [
        ('Tape',            lambda i: i[0]),
        ('# Files',         lambda i: i[1]),
        ('Remaining Size',  lambda i: Tools.convert_size(i[2])),
    ]

    # continue one round of a given restore job
    # if no job id is given, use the latest job
    # one round consists of:
    #   1) query the library for available tapes
    #   2) get a list of all files to restore from these tapes
    #   3) restore the files to the configured target directory
    #   4) determine a list of tapes to load for the next round
    #      and prompt the user to load these
    def cont(self, jobid=None):
        if jobid is None:
            self.set_latest_job()
        else:
            self.jobid = jobid

        tag_in_tapelib, tags_to_remove_from_library = self.tapelibrary.get_tapes_tags_from_library(self.session)
        tapes = tag_in_tapelib + tags_to_remove_from_library

        files = database.get_restore_job_files(self.session, self.jobid, tapes, restored=False)
        if files:
            logger.info(f'Restoring {len(files)} files from the loaded tapes')
            self.restore_files(files)
        else:
            logger.info("No files to restore on the loaded tapes")

        next_tapes = self.make_next_tapes_info()
        if next_tapes:
            Tools.table_print(next_tapes, self.table_format_next_tapes)
            print(f'Full tapes to remove: {", ".join(tags_to_remove_from_library)}')
        else:
            logger.info("No more files to restore. Restore job complete.")
            database.set_restore_job_finished(self.session, self.jobid)

    def abort(self, jobid=None):
        if jobid is None:
            self.set_latest_job()
        else:
            self.jobid = jobid

        if self.jobid is None:
            logger.error("No restore job available")
            sys.exit(1)
        else:
            logger.info(f"Deleting restore job {self.jobid}")
            database.delete_restore_job(self.session, self.jobid)

    table_format_list = [
        ('Job ID',          lambda i: i[0]),
        ('Started',         lambda i: i[1]),
        ('Remaining Files', lambda i: i[3]),
        ('Remaining Size',  lambda i: i[4]),
    ]

    def list(self):
        stats_r = database.get_restore_job_stats_remaining(self.session)
        Tools.table_print(stats_r, self.table_format_list)

    table_format_status = [
        ('#',           lambda i: i[-1]),
        ('Files',       lambda i: i[3]),
        ('Filesize',    lambda i: Tools.convert_size(i[4]) if isinstance(i[4], int) else i[4]),
        ('Tapes',       lambda i: i[5]),
    ]

    table_format_status_files = [
        ('Filename',    lambda i: i.filename),
        ('Filesize',    lambda i: Tools.convert_size(i.filesize)),
        ('Tape',        lambda i: i.tape.label),
        ('Restored',    lambda i: 'Yes' if i.restoreJobFileMap.restored else 'No'),
    ]

    def status(self, jobid=None, verbose=False):
        if jobid is None:
            self.set_latest_job()
        else:
            self.jobid = jobid

        if not self.jobid:
            logging.error("No restore job available")
            sys.exit(1)

        table = []
        stats_t = database.get_restore_job_stats_total(self.session, self.jobid)[0]
        stats_r = database.get_restore_job_stats_remaining(self.session, self.jobid)
        if stats_r:
            stats_r = stats_r[0]
        else:
            stats_r = [0]*6
        table_data = [list(stats_t) + ["Total"]]
        table_data += [[None]*3 + [
            f"{stats_r[3]} ({stats_r[3]/stats_t[3]*100:.2f}%)",
            f"{Tools.convert_size(stats_r[4])} ({stats_r[4]/stats_t[4]*100:.2f}%)",
            f"{stats_r[5]} ({stats_r[5]/stats_t[5]*100:.2f}%)",
            "Remaining"
        ]]
        Tools.table_print(table_data, self.table_format_status)

        if verbose:
            files = database.get_restore_job_files(self.jobid, restored=True)
            Tools.table_print(files, self.table_format_status_files)

    def read_filelist(self, filelist):
        logger.info(f'Reading filelist {filelist}')
        with open(filelist, "r") as f:
            return [l.rstrip("\n") for l in f]

    def set_latest_job(self):
        job = database.get_latest_restore_job(self.session)
        if job is not None:
            self.jobid = job.id
        else:
            logger.error('No restore job available')
            sys.exit(1)

    # get file ids for a list of files from the database,
    # warn if some do not exist and optionally filter by a tape name
    def resolve_file_ids(self, files, tape=None):
        logger.debug(f'Resolving {len(files)} files in database')
        db_files = database.get_files_like(self.session, files, tape, written=True)
        for file in files:
            # don't check wildcard files
            if '%' in file:
                continue
            if not any(f.path == file for f in db_files):
                logger.warning(f'File {file} not found')
        return [f.id for f in db_files]

    # restores a list of files from database
    def restore_files(self, files):
        tapes_files = self.group_files_by_tape(files)
        for tape, files in tapes_files.items():
            self.restore_from_tape(tape, files)
            if self.interrupted:
                break

    def restore_from_tape(self, tape, files):
        logger.info(f'Restoring from tape {tape}')
        self.tapelibrary.load(tape)
        self.tapelibrary.ltfs()

        ordered_files = self.tools.order_by_startblock(files)
        for file in ordered_files:
            self.restore_single_file(file)
            if self.interrupted:
                logging.info(f'Restore interrupted')
                break

        logger.info(f'Restoring from tape {tape} done')
        self.tapelibrary.unload()

    # returns a dictionary containing {tape: (n_files, files_size)}
    def make_next_tapes_info(self):
        files = database.get_restore_job_files(self.session, self.jobid, restored=False)
        tapes = dict()
        for file in files:
            if not file.filesize:
                size = 0
            else:
                size = file.filesize
            info = (tapes[file.tape.label][0] + 1, tapes[file.tape.label][1] + size) \
                    if file.tape.label in tapes else (1, size)
            tapes[file.tape.label] = info
        return list((x, *y) for x, y in sorted(tapes.items(), key=lambda i: i[0]))

    def group_files_by_tape(self, files):
        grouped = dict()
        for file in files:
            tape = file.tape.label
            if tape in grouped:
                grouped[tape] += [file]
            else:
                grouped[tape] = [file]
        return grouped

    def restore_single_file(self, file):
        logger.info(f'Restoring {file.path}')
        success = self.encryption.decrypt_relative(file.filename_encrypted, file.path, mkdir=True)
        if success:
            logger.debug(f'Restored {file.path} successfully')
            database.set_file_restored(self.session, self.jobid, file.id)
        else:
            logger.error(f'Restoring {file.path} failed')
