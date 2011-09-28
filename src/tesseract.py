#!/usr/bin/env python
'''
Python-tesseract is an optical character recognition (OCR) tool for python.
That is, it will recognize and "read" the text embedded in images.

Python-tesseract is a wrapper for google's Tesseract-OCR
( http://code.google.com/p/tesseract-ocr/ ).  It is also useful as a
stand-alone invocation script to tesseract, as it can read all image types
supported by the Python Imaging Library, including jpeg, png, gif, bmp, tiff,
and others, whereas tesseract-ocr by default only supports tiff and bmp.
Additionally, if used as a script, Python-tesseract will print the recognized
text in stead of writing it to a file. Support for confidence estimates and
bounding box data is planned for future releases.


USAGE:
From the shell:
 $ ./tesseract.py test.png                  # prints recognized text in image
 $ ./tesseract.py -l fra test-european.jpg  # recognizes french text
In python:
 > import Image
 > from tesseract import image_to_string
 > print image_to_string(Image.open('test.png'))
 > print image_to_string(Image.open('test-european.jpg'), lang='fra')


INSTALLATION:
* Python-tesseract requires python 2.5 or later.
* You will need the Python Imaging Library (PIL).  Under Debian/Ubuntu, this is
  the package "python-imaging".
* Install google tesseract-ocr from http://code.google.com/p/tesseract-ocr/ .
  You must be able to invoke the tesseract command as "tesseract". If this
  isn't the case, for example because tesseract isn't in your PATH, you will
  have to change the "tesseract_cmd" variable at the top of 'tesseract.py'.


COPYRIGHT:
Python-tesseract is released under the GPL v3.
Copyright (c) Samuel Hoffstaetter, 2009
http://wiki.github.com/hoffstaetter/python-tesseract

'''

# CHANGE THIS IF TESSERACT IS NOT IN YOUR PATH, OR IS NAMED DIFFERENTLY
tesseract_cmd = 'tesseract'

import Image
import StringIO
import subprocess
import sys
import os

__all__ = ['image_to_string']

def run_tesseract(input_filename, output_filename_base, lang=None, boxes=False):
    '''
    runs the command:
        `tesseract_cmd` `input_filename` `output_filename_base`
    
    returns the exit status of tesseract, as well as tesseract's stderr output

    '''

    command = [tesseract_cmd, input_filename, output_filename_base]
    
    if lang is not None:
        command += ['-l', lang]

    if boxes:
        command += ['batch.nochop', 'makebox']

    proc = subprocess.Popen(command,
            stderr=subprocess.PIPE)
    # XXX(Jflesch): In some cases, tesseract may print more on stderr than
    # allowed by the buffer of subprocess.Popen.stderr. So we must read stderr
    # asap or Tesseract will remain stuck when trying to write again on stderr.
    # In the end, we just have to make sure that proc.stderr.read() is called
    # before proc.wait()
    errors = proc.stderr.read()
    return (proc.wait(), errors)

def cleanup(filename):
    ''' tries to remove the given filename. Ignores non-existent files '''
    try:
        os.remove(filename)
    except OSError:
        pass

def get_errors(error_string):
    '''
    returns all lines in the error_string that start with the string "error"

    '''

    lines = error_string.splitlines()
    error_lines = tuple(line for line in lines if line.find('Error') >= 0)
    if len(error_lines) > 0:
        return '\n'.join(error_lines)
    else:
        return error_string.strip()

def tempnam():
    ''' returns a temporary file-name '''

    # prevent os.tmpname from printing an error...
    stderr = sys.stderr
    try:
        sys.stderr = StringIO.StringIO()
        return os.tempnam(None, 'tess_')
    finally:
        sys.stderr = stderr

class TesseractError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        self.args = (status, message)

class TesseractBox(object):
    def __init__(self, box_position, page):
        self.string = u""
        self.box_position = box_position
        self.page = page

    def add_char(self, char):
        self.string += char

    def get_char(self):
        return self.char

    def get_xy(self):
        return self.box_position

    def get_top_left_point(self):
        return self.box_position[0]

    def get_bottom_right_point(self):
        return self.box_position[1]

    def get_width(self):
        return self.box_position[1][0] - self.box_position[0][0]

    def get_height(self):
        return self.box_position[1][1] - self.box_position[0][1]

    def get_page(self):
        return page

    def __str__(self):
        return "%s %d %d %d %d %d" % (
            self.string,
            self.box_position[0][0],
            self.box_position[0][1],
            self.box_position[1][0],
            self.box_position[1][1],
            self.page
        )

def read_boxes(file_descriptor):
    """
    Extract of set of TesseractBox from the lines of 'file_descriptor'
    """
    position_to_box = { } # to figure out which characters go into which box
    boxes = [] # to keep the order of the boxes
    for line in file_descriptor.readlines():
        line = line.strip()
        if line == "":
            continue
        el = line.split(" ")
        if len(el) < 6:
            continue
        position = ((int(el[1]), int(el[2])),
                    (int(el[3]), int(el[4])))
        box = TesseractBox(position, int(el[5]))
        boxes.append(box)
        box.add_char(unicode(el[0]))
    return boxes

def write_box_file(file_descriptor, boxes):
    """
    Write boxes in a box file. Output is in a the same format than tesseract's one.
    """
    for box in boxes:
        file_descriptor.write(str(box) + "\n")


def image_to_string(image, lang=None, boxes=False):
    '''
    Runs tesseract on the specified image. First, the image is written to disk,
    and then the tesseract command is run on the image. Tesseract's result is
    read, and the temporary files are erased.

    Returns:
        if boxes == False (default): the text as read from the image
        if boxes == True: an array of TesseractBox

    '''

    input_file_name = '%s.bmp' % tempnam()
    output_file_name_base = tempnam()
    if not boxes:
        output_file_name = '%s.txt' % output_file_name_base
    else:
        output_file_name = '%s.box' % output_file_name_base
    try:
        image.save(input_file_name)
        (status, errors) = run_tesseract(input_file_name,
                                         output_file_name_base,
                                         lang=lang,
                                         boxes=boxes)
        if status:
            raise TesseractError(status, errors)
        f = open(output_file_name)
        try:
            if not boxes:
                return f.read().strip()
            else:
                return read_boxes(f)
        finally:
            f.close()
    finally:
        cleanup(input_file_name)
        cleanup(output_file_name)

if __name__ == '__main__':
    if len(sys.argv) == 2:
        filename = sys.argv[1]
        try:
            image = Image.open(filename)
        except IOError:
            sys.stderr.write('ERROR: Could not open file "%s"\n' % filename)
            exit(1)
        print image_to_string(image)
    elif len(sys.argv) == 4 and sys.argv[1] == '-l':
        lang = sys.argv[2]
        filename = sys.argv[3]
        try:
            image = Image.open(filename)
        except IOError:
            sys.stderr.write('ERROR: Could not open file "%s"\n' % filename)
            exit(1)
        print image_to_string(image, lang=lang)
    else:
        sys.stderr.write('Usage: python tesseract.py [-l language] input_file\n')
        exit(2)
