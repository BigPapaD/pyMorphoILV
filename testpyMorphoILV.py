#!/usr/bin/env python
# -*- coding: utf-8 -*-

import atexit
import signal
import sys

import array
import pyMorphoILV

try:
  import nfiq
except ImportError:
  nfiq_available = False
  print 'NFIQ not available install from: https://github.com/alromh87/NBIS-python'
else:
  nfiq_available = True

#from queue import Queue
from multiprocessing import Queue
from threading import Thread
import threading

from PIL import Image

def signal_term_handler(signal, frame):
  print 'got SIGTERM'
  exit_handler()
 
signal.signal(signal.SIGTERM, signal_term_handler)

def exit_handler():
  print 'My application is ending!'
  try:
    morph.close()
    readThread.do_run = False
    readThread.join()
  except NameError:
    pass
  sys.exit(0)

atexit.register(exit_handler)

try:
  morph = pyMorphoILV.Terminal()
except ValueError as e:
  print e
  print "\n\n------------------------\n Morpho reader not found \n------------------------\n\n" 
  sys.exit(0)

# A thread that consumes data
def consumer(in_q):
  t = threading.currentThread()
  tarea = ""
  expediente = ""
  huella64 = ""
  while getattr(t, "do_run", True):
    if not in_q.empty():
      data = in_q.get()
      if data is not None:
        print data['status']
        if data['status'] == 'huellaf':
          img = Image.frombuffer('L', [data['data']['colNumber'], data['data']['rowNumber']], data['data']['huella'], "raw", 'L', 0, 1)
          img.show()

          print '\nHuella obtenida: \n'
          if nfiq_available:
            result =  nfiq.comp_nfiq(data['data']['huella'],  data['data']['colNumber'],  data['data']['rowNumber'], 8, 500)
            print '\tCalidad:', result[1]

          with open("fingerprint.raw", 'wb') as raw_file:
            raw_file.write(data['data']['huella'])
      else:
        print data
      print '\n--------------------------------------------------------\n'

  print "Hilo recepción terminado"

q = Queue()
readThread = Thread(target=consumer, args=(q,))
readThread.start()

morph.startRead(q)

try:
  while(True):
    entrada = raw_input(">")
    if entrada == "scan":
      morph.getFingerPrint()
    elif entrada == "enroll":
      print "TODO: Enroll unimplemented"
      #morph.enroll()
    elif entrada == "verify":
      print "TODO: Verify unimplemented"
      #morph.verify()
    elif entrada == "identify":
      print "TODO: Identify unimplemented"
      #morph.identify()
    elif entrada == "info":
      morph.getInfo()
    elif entrada == "exit":
      exit_handler()
    else:
      print "Available commands: \n\t scan \n\t enroll \n\t verify \n\t identify \n\t info \n\t exit"
 
except KeyboardInterrupt:
  exit_handler()
