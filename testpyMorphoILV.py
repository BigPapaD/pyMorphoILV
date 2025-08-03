#!/usr/bin/env python
# -*- coding: utf-8 -*-

import atexit
import signal
import sys
import os
from datetime import datetime

import array
import pyMorphoILV

try:
  import nfiq
except ImportError:
  nfiq_available = False
  print('NFIQ not available install from: https://github.com/alromh87/NBIS-python')
else:
  nfiq_available = True

#from queue import Queue
from multiprocessing import Queue
from threading import Thread
import threading

from PIL import Image

def signal_term_handler(signal, frame):
  print('got SIGTERM')
  exit_handler()
 
signal.signal(signal.SIGTERM, signal_term_handler)

def exit_handler():
  print('My application is ending!')
  try:
    morph.close()
    readThread.do_run = False
    readThread.join()
  except NameError:
    pass
  sys.exit(0)

atexit.register(exit_handler)

# Create output directory if it doesn't exist
output_dir = "output"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Created output directory: {output_dir}")

try:
  morph = pyMorphoILV.Terminal()
except ValueError as e:
  print(e)
  print("\n\n------------------------\n Morpho reader not found \n------------------------\n\n") 
  sys.exit(0)

# A thread that consumes data
def consumer(in_q):
  t = threading.current_thread()
  task = ""
  record = ""
  fingerprint64 = ""
  while getattr(t, "do_run", True):
    if not in_q.empty():
      data = in_q.get()
      if data is not None:
        print(data['status'])
        if data['status'] == 'fingerprintf':
          img = Image.frombuffer('L', [data['data']['colNumber'], data['data']['rowNumber']], data['data']['fingerprint'], "raw", 'L', 0, 1)
          
          # Generate filename with current date and time
          timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
          image_filename = f"fingerprint_{timestamp}.png"
          raw_filename = f"fingerprint_{timestamp}.raw"
          
          # Save PNG image to output folder
          image_path = os.path.join(output_dir, image_filename)
          img.save(image_path)
          print(f'Fingerprint image saved to: {image_path}')
          
          # Also show the image
          img.show()

          print('\nFingerprint obtained: \n')
          if nfiq_available:
            result =  nfiq.comp_nfiq(data['data']['fingerprint'],  data['data']['colNumber'],  data['data']['rowNumber'], 8, 500)
            print('\tQuality:', result[1])

          # Save raw data to output folder
          raw_path = os.path.join(output_dir, raw_filename)
          with open(raw_path, 'wb') as raw_file:
            raw_file.write(data['data']['fingerprint'])
          print(f'Raw fingerprint data saved to: {raw_path}')
      else:
        print(data)
      print('\n--------------------------------------------------------\n')

  print("Reception thread finished")

q = Queue()
readThread = Thread(target=consumer, args=(q,))
readThread.start()

morph.startRead(q)

try:
  while(True):
    command = input(">")
    if command == "scan":
      morph.getFingerPrint()
    elif command == "enroll":
      print("TODO: Enroll unimplemented")
      #morph.enroll()
    elif command == "verify":
      print("TODO: Verify unimplemented")
      #morph.verify()
    elif command == "identify":
      print("TODO: Identify unimplemented")
      #morph.identify()
    elif command == "info":
      morph.getInfo()
    elif command == "exit":
      exit_handler()
    else:
      print("Available commands: \n\t scan \n\t enroll \n\t verify \n\t identify \n\t info \n\t exit")
 
except KeyboardInterrupt:
  exit_handler()
