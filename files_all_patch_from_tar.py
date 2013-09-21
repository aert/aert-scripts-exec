#!/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
from optparse import OptionParser
from os import path
from shutil import rmtree, copy2
import csv
import os
import sys
import tarfile
import difflib
import subprocess
import logging

DIR_BASE = path.expandvars("$HOME/__patch_from_tar__/")
DIR_WORKING = path.join(DIR_BASE, datetime.now().strftime("%Y-%m-%d_%H%M%S"))
DIR_WORKING_EXTRACTED = path.join(DIR_WORKING, "extracted")
DIRNAME_META = 'META-INF'
DIRNAME_META_OLDFILES = '{0}/oldfiles'.format(DIRNAME_META)
DIRNAME_META_PATCHS = '{0}/patches'.format(DIRNAME_META)
FILENAME_MANIFEST = 'MANIFEST.mf'


def setup_logging(dir_name, filename="REPORT.log"):
    '''
    Enables stdout redirection to file and terminal.
    '''
    # set up logging to file - see previous section for more details
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y%m%d-%H:%M:%S',
                        filename=path.join(dir_name, filename),
                        filemode='w')
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s',
                                  '%H:%M:%S')
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)


def task_build_tar(source_dir, tar_archive):
    '''
    Validates source_dir and builds tar_archive on success
    :param source_dir: input source dir, using gp3-patcher convention
    :param tar_archive: output compressed archive
    '''

    dir_meta = path.join(source_dir, DIRNAME_META)
    dir_meta_oldfiles = path.join(source_dir, DIRNAME_META_OLDFILES)
    dir_meta_patchs = path.join(source_dir, DIRNAME_META_PATCHS)
    # create META folder structure
    if path.isdir(dir_meta):
        rmtree(dir_meta)
    os.makedirs(dir_meta_oldfiles)
    os.makedirs(dir_meta_patchs)

    setup_logging(dir_name=dir_meta)

    logging.info("### task: BUILD TAR ###")
    # validate source_dir structure
    if not _validate_patch_dir(source_dir):
        return 1

    logging.info("Valid patch dir detected, generating meta-data ...")

    # copy old files to META-INF/oldfiles
    # and generate patch to META-INF/patches
    manifest_path = path.join(source_dir, FILENAME_MANIFEST)
    manifest_reader = csv.reader(open(manifest_path, "rb"),
                                 delimiter=';', quotechar="'")
    i = 0
    for row in manifest_reader:
        i = i + 1

        fmodified_path = path.join(source_dir, row[0])
        foriginal_path = my_expandvars(row[1])
        is_newfile = True if row[2] == "Y" else False

        backup_key = row[0]
        fdiff_path = path.join(dir_meta_patchs, backup_key + ".patch")

        row_result = 0

        # copy original file if not new file
        if not is_newfile:
            # backup original file
            fbkup_path = path.join(dir_meta_oldfiles, backup_key)
            if not path.isdir(path.dirname(fbkup_path)):
                os.makedirs(path.dirname(fbkup_path))
            copy2(foriginal_path, fbkup_path)
            # diff files
            lines_original = open(foriginal_path).readlines()
            lines_modified = open(fmodified_path).readlines()
            diff_lines = _diff_files(lines_original, lines_modified)

            if not path.isdir(path.dirname(fdiff_path)):
                os.makedirs(path.dirname(fdiff_path))
            fdiff = open(fdiff_path, 'w')
            fdiff.writelines(diff_lines)
            fdiff.close()

            if len(diff_lines) < 1:
                logging.warning("{0}[{1}] ({2}) no changes detected"
                                .format(FILENAME_MANIFEST, i, row[0]))
                row_result = 1
        if row_result == 0:
            logging.debug("OK> {0}[{1}] : {2}".format(FILENAME_MANIFEST,
                                                      i, row[0]))

    # tar source_dir
    logging.info("Creating tar archive ...")
    tar = tarfile.open(tar_archive, "w:gz")
    tar.add(source_dir, arcname="")
    tar.close()

    if path.isdir(dir_meta):
        rmtree(dir_meta)

    return 0


def task_dry_run(tar_archive):
    _create_working_dir()
    logging.info("### task: DRY RUN ###")

    if not _uncompress_and_validate(tar_archive):
        logging.error("Patch can not be applied on this system.")
        return 1
    else:
        logging.info("Patch can be applied on system.")
        return 0


def task_safe_run(tar_archive):
    _create_working_dir()
    logging.info("### task: SAFE RUN ###")

    if not _uncompress_and_validate(tar_archive):
        logging.error("Patch can not be applied on this system.")
        return 1

    logging.info("Valid archive detected, applying patchs ...")

    # lecture du fichier manifest
    manifest_path = path.join(DIR_WORKING_EXTRACTED, FILENAME_MANIFEST)
    manifest_reader = csv.reader(open(manifest_path, "rb"),
                                 delimiter=';', quotechar="'")
    i = 0
    result = True
    for row in manifest_reader:
        i = i + 1
        row_result = True

        # compute paths
        dir_meta_patchs = path.join(DIR_WORKING_EXTRACTED, DIRNAME_META_PATCHS)
        backup_key = row[0]
        fdiff_path = path.join(dir_meta_patchs, backup_key + ".patch")
        foriginal_path = my_expandvars(row[1])
        is_newfile = True if row[2] == "Y" else False

        # apply patch
        if not is_newfile:
            lines_patch = open(fdiff_path).readlines()
            _apply_diff(lines_patch, foriginal_path)
        else:
            fmodified_path = path.join(DIR_WORKING_EXTRACTED, row[0])
            if not path.isdir(path.dirname(foriginal_path)):
                os.makedirs(path.dirname(foriginal_path))
            copy2(fmodified_path, foriginal_path)

        if row_result:
            logging.info("PATCHED > {0}[{1}] ({2})".format(FILENAME_MANIFEST,
                                                           i, row[0]))
        else:
            result = False

    if result:
        logging.info("All patchs applied successfully.")
    return result


def _create_working_dir():
    '''
    Creates report dir if it doesn't exist and setups logging
    '''
    if path.isdir(DIR_WORKING):
        return
    os.makedirs(DIR_WORKING)
    setup_logging(DIR_WORKING)

    print "Created DIR_WORKING: '{0}' ...".format(DIR_WORKING)


def _validate_patch_dir(source_dir, with_metas=False):
    '''
    Checks if source_dir follows gp3-patcher convention and that <listing.txt>
    can be applied on system
    :param source_dir: input source dir, using gp3-patcher convention
    :param with_metas: indicates if meta-inf subdirs should be checked
    '''
    logging.info("Validating patch list ...")

    # check that <listing.txt> exists
    manifest_path = path.join(source_dir, FILENAME_MANIFEST)
    if not path.isfile(manifest_path):
        logging.error("FATAL> {0} not found in tar content"
                      .format(FILENAME_MANIFEST))
        return False

    # validate <listing.txt>
    manifest_reader = csv.reader(open(manifest_path, "rb"),
                                 delimiter=';', quotechar="'")
    i = 0
    result = True
    for row in manifest_reader:
        i = i + 1
        if len(row) != 3:
            logging.error("FATAL>  {0} : line {1}, incorrect line format"
                          .format(FILENAME_MANIFEST, i))
            return False

        fmodified_path = path.join(source_dir, row[0])
        foriginal_path = my_expandvars(row[1])
        is_newfile = True if row[2] == "Y" else False

        row_result = True
        if not path.isfile(fmodified_path):
            logging.error("{0}[{1}] ({2}) modified file not found"
                          .format(FILENAME_MANIFEST, i, row[0]))
            row_result = False
        if is_newfile and path.isfile(foriginal_path):
            logging.error("{0}[{1}] ({2}) target file shouldn't exist"
                          .format(FILENAME_MANIFEST, i, row[0]))
            row_result = False
        elif not is_newfile and not path.isfile(foriginal_path):
            logging.error("{0}[{1}] ({2}) target file not found ({3})"
                          .format(FILENAME_MANIFEST, i, row[0], foriginal_path))
            row_result = False

        # validate meta-inf subdir
        if with_metas:
            dir_meta_oldfiles = path.join(source_dir, DIRNAME_META_OLDFILES)
            dir_meta_patchs = path.join(source_dir, DIRNAME_META_PATCHS)
            backup_key = row[0]
            fdiff_path = path.join(dir_meta_patchs, backup_key + ".patch")
            fmeta_original_path = path.join(dir_meta_oldfiles, backup_key)

            if not is_newfile and not path.isfile(fdiff_path):
                logging.error("{0}[{1}] ({2}) patch file not found"
                              .format(FILENAME_MANIFEST, i, row[0]))
                row_result = False

            if not is_newfile and not path.isfile(fmeta_original_path):
                logging.error(("{0}[{1}] ({2}) original file not found "
                               "in meta-inf").format(FILENAME_MANIFEST, i, row[0]))
                row_result = False

            # checking access rights
            if row_result:
                if is_newfile:
                    if not os.access(path.dirname(foriginal_path), os.W_OK):
                        logging.error(("{0}[{1}] ({2}) no write access to"
                                       " target dir").format(FILENAME_MANIFEST,
                                                             i, row[0]))
                        row_result = False
                else:
                    if not os.access(foriginal_path, os.W_OK):
                        logging.error(("{0}[{1}] ({2}) no write access to"
                                       " target file").format(FILENAME_MANIFEST,
                                                              i, row[0]))
                        row_result = False

            # patch validation
            if row_result and not is_newfile:
                # diff files
                lines_meta_original = open(fmeta_original_path).readlines()
                lines_original = open(foriginal_path).readlines()
                diff_lines = list(difflib.unified_diff(lines_meta_original,
                                                       lines_original,
                                                       fromfile="expected file",
                                                       tofile="actual file",
                                                       n=0))
                if len(diff_lines) > 0:
                    logging.error(("{0}[{1}] ({2}) target file content is not"
                                   " valid :\n{3}")
                                  .format(FILENAME_MANIFEST,
                                          i, row[0], " " * 18 +
                                          (" " * 18).join(diff_lines).rstrip()))
                    row_result = False

        if row_result:
            logging.debug("OK> {0}[{1}] ({2})".format(FILENAME_MANIFEST,
                                                      i, row[0]))
        else:
            result = False
    return result


def _uncompress_and_validate(tar_archive):
    '''
    Uncompresses archive and validates it's content.
    :param tar_archive: tar archive to be processed
    '''
    logging.info("Uncompressing tar file ...")

    if not tarfile.is_tarfile(tar_archive):
        logging.error("FATAL> Not a tar archive file")
        return False

    # uncompressing to DIR_WORKING_EXTRACTED folder
    tar = tarfile.open(tar_archive, "r:*")
    tar.extractall(DIR_WORKING_EXTRACTED)
    tar.close()

    # validate patch
    return _validate_patch_dir(DIR_WORKING_EXTRACTED, with_metas=True)


def my_expandvars(path):
    return subprocess.Popen('. $HOME/sc_init.exe && echo "' + path + '"',
                            stdout=subprocess.PIPE,
                            shell=True).communicate()[0].rstrip()


def _diff_files(original_lines, modified_lines):
    return list(difflib.ndiff(original_lines, modified_lines))


def _apply_diff(patch_lines, dest_file):
    patched = difflib.restore(patch_lines, 2)

    with open(dest_file, "w") as f:
        f.writelines(patched)


def main():
    '''
    Main processing
    '''
    usage = "Usage: %prog [options] archive.tar"
    parser = OptionParser(usage=usage, version="%prog 1.0")

    # Dry Run
    parser.add_option("-t", "--dry-run",
                      action="store_const", const=1, default=0,
                      dest="dry_run",
                      help=("run the patcher in test mode,"
                            " without applying patches"))

    # Safe Run
    parser.add_option("-r", "--safe-run",
                      action="store_const", const=1, default=0,
                      dest="safe_run",
                      help="run the patcher, ignoring non applicable changes")

    # Build Tar
    parser.add_option("-b", "--build-tar",
                      action="store",
                      dest="build_tar",
                      metavar="source_dir",
                      help=("validates source_dir and builds"
                            " tar_archive on success"))

    (options, args) = parser.parse_args()

    if len(sys.argv) <= 1:
        parser.print_help()
        return 2

    # Check args
    build_tar = 0 if options.build_tar is None else 1
    if options.dry_run + options.safe_run + build_tar > 1:
        parser.error("mutually exclusive options detected")
    elif len(args) != 1:
        parser.error("incorrect number of arguments")
    elif options.dry_run + options.safe_run + build_tar == 0:
        parser.error("no action specified")
    elif build_tar and not options.build_tar:
        parser.error("source_dir unspecified")

    # Processing
    out = 1  # error if no action specified
    if options.dry_run:
        out = task_dry_run(args[0])
    elif options.safe_run:
        out = task_safe_run(args[0])
    elif options.build_tar:
        out = task_build_tar(options.build_tar, args[0])

    if out == 0:
        logging.info("Done.")

    return out


if __name__ == "__main__":
    out = main()
    sys.exit()
