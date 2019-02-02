#!/usr/bin/env python
# -*- coding: utf-8 -*-

import usb.core
import usb.util
import usb.control

import array
import atexit

from threading import Thread
import threading

def_vendID=0x079b
def_prodID=0x0024
def_baudrate=38400
def_endPOut=0x02
def_endPIn=0x83

knownMorphoTerminals = [
                         {'name':'MSO300',  'prodID':0x0024},
                         {'name':'CBM OEM', 'prodID':0x0047}
                       ]

class Terminal(object):
  def __init__(self, vendID=def_vendID, prodID=0, baudrate=def_baudrate, endPOut=def_endPOut, endPIn = def_endPIn):
    print "Starting Morpho Terminal"
    # Look for a specific device and open it
    if prodID == 0:
      found = searchTerminal()
      if len(found)==0:
        raise ValueError('No morpho terminal found!!')
      else:
        print found[0][1]
        dev = found[0][0]
        baudrate, endPOut, endPIn = paramsFromFound(found[0][1])
#        print "Found! inicializar %d,%d,%d"%(baudrate, endPOut, endPIn)
    else:
      dev = usb.core.find(idVendor=vendID, idProduct=prodID)
      if dev is None:
        raise ValueError('Requested morpho terminal not found!!')

    # Detach interfaces if Linux already attached a driver on it.
    for itf_num in [0, 1]:
      itf = usb.util.find_descriptor(dev.get_active_configuration(),
                                  bInterfaceNumber=itf_num)
      if dev.is_kernel_driver_active(itf):
          dev.detach_kernel_driver(itf)
      usb.util.claim_interface(dev, itf)


    # set control line state 0x2221
    # set line encoding 0x2021 (baudrate, 8N1)
    extra = array.array('B', [0x00, 0x00, 0x08])
    baud = int2array(baudrate)
    baud.extend(extra)

    dev.ctrl_transfer(0x21, 0x22, 0x01 | 0x02, 0, None)
    dev.ctrl_transfer(0x21, 0x20, 0, 0, baud)

    self.lector = dev
    self.endPOut = endPOut
    self.endPIn  = endPIn
    self.ILVCommand = 0x00
    atexit.register(self.exit_handler)

  @classmethod
  def fromFound(cls, found):
     vendID = found[1]['vendID']
     prodID = found[1]['prodID']
     baudrate, endPOut, endPIn = paramsFromFound(found[1])
     return cls(vendID, prodID, baudrate, endPOut, endPIn)

  def sendILV(self, data):
    # Send SYNC
    payload = headerData = bytearray(B"SYNC");

    # Send data size and two's complement
    dataSize = len(data);
    cDataSize = -(dataSize+1);
    payload.extend(int2array(dataSize))
    payload.extend(int2array(cDataSize))
    # Send command
    payload.extend(data);
    # Send EN
    tailData = bytearray("EN");
    payload.extend(tailData)

    self.lector.write(self.endPOut, payload, interface = 1)
    if __debug__:
      print "Sending: ", ":".join("{:02x}".format(c,'02x') for c in payload)

  def startRead(self, q):
    readThread = Thread(target=self.read, args=(q,))
    readThread.start()
    self.readThread = readThread

  def read(self, out_q):
    t = threading.currentThread()
    serialReading = False
    serialErrorReported = False
    while getattr(t, "do_run", True):
      try:
        data = self.lector.read(self.endPIn, 1024, interface = 1)
        #print 'Back: "%s"' % ":".join("{:02x}".format(c) for c in data)
        if not serialReading: #Start reading buffer
          if len(data) < 6:
            out_q.put({'status':'Error','data':'Comunication error with biometric reader'})
	    continue
          if data[0] == 0x53 and data[1] == 0x59 and data[2] == 0x4E and data[3] == 0x43: #Header found, start reading
	    #print "'SYNC' found"
            if data[-1]==0x4E and data[-2]==0x45: #End found, process complete chunk
              out_q.put(self.processILV(data, len(data), 12))
            else: #Else, start new reading buffer
              serialData    = data
              serialReading = True
            serialErrorReported = False
          else:
            if not serialErrorReported :
              out_q.put({'status':'Error','data':"'SYNC' not found"})
              serialErrorReported = True
        else:
          serialData.extend(data)
          if data[-1]==0x4E and data[-2]==0x45: # End found, read completed
            #print "reading ended"
            out_q.put(self.processILV(serialData, len(serialData), 12))
            serialReading = False
      except usb.core.USBError as e:
        #print e
        pass
    print("Morpho Reading Stopped.")


  # Commands
  def getInfo(self):
    data = array.array('B', [0x05, 0x01, 0x00, 0x2F])
    self.sendILV(data)

  def getFingerPrint(self):

    longitud	= 8+7+9+4
    base        = 0x00
    espera      = 0x07
    calidad     = 0x00
    pasadas     = 0x01
    dedos       = 0x01
    guardar     = 0x00
    tamano      = 0x00

    # Image
    data = array.array('B', [0x21])
    data.extend(short2array(longitud))
    data.extend(array.array('B',[base]))
    data.extend(short2array(espera))
    data.extend(array.array('B',[calidad, pasadas, dedos, guardar, tamano]))
    #   Asynchronous event ILV
    idEvent	= 0x34 #ID_ASYNCHRONOUS_EVENT
    size	= 4
    command	= 0x03 #(COMMAND) | (IMAGE) // | ¿(CODE_QUALITY)?

    data.extend(array.array('B',[idEvent]))
    data.extend(short2array(size))
    data.extend(array.array('B',[command, 0x00, 0x00, 0x00]))

    # Export Image ILV
    idEvent	= 0x3D #ID_EXPORT_IMAGE
    size	= 6
    imageType	= 0x00 #ID_DEFAULT_IMAGE
    
    data.extend(array.array('B',[idEvent]))
    data.extend(short2array(size))
    data.extend(array.array('B',[imageType]))
    #  Compression ILV
    idEvent	= 0x3E #ID_COMPRESSION 
    size	= 2
    command	= 0x2C #ID_COMPRESSION_NULL
    data.extend(array.array('B',[idEvent]))
    data.extend(short2array(size))
    data.extend(array.array('B',[command, 0x00]))

    # Latent fingerprint ILV
    idEvent	= 0x39 #ID_LATENT_SETTING
    size	= 1
    command	= 0x01 #ENABLED
    data.extend(array.array('B',[idEvent]))
    data.extend(short2array(size))
    data.extend(array.array('B',[command]))
    self.sendILV(data)

  def createDB(self):    #TODO
    longitud          = 5;
    maximoRegistros   = 100;

    data = array.array('B', [0x30])
    data.extend(short2array(longitud))
    data.extend(array.array('B',[0x00, 0x00]))
    data.extend(short2array(maximoRegistros))
    data.extend(array.array('B',[0x02]))
    self.sendILV(data);

  def deleteDB(self):    #TODO
    data = array.array('B', [0x33, 0x01, 0x00, 0x00])
    self.sendILV(data);
    
  def processILV(self, buffer, size, offset):
    ILV_OK 		= 0x00
    ILVERR_CMDE_ABORTED	= 0xE5;
    
    ILVSTS_OK		= 0x00;
    ILVSTS_HIT		= 0x01;
    ILVSTS_NO_HIT	= 0x02;
    ILVSTS_DB_FULL	= 0x04;
    ILVSTS_DB_EMPTY	= 0x05;
    ILVSTS_FFD		= 0x22;
    ILVSTS_MOIST_FINGER	= 0x23;

    if buffer[offset] == 0x50:
      print "Invalid ILV command"
    else:
      code = buffer[offset];
      longitud = (buffer[offset+1]&0xFF) + ((buffer[offset+2]<<8)&0xFF00);
      if longitud==65535: # Bigger message, use 4 bytes
        offset+=2
	longitud = (buffer[offset+1]&0xFF) + ((buffer[offset+2]<<8)&0xFF00) + ((buffer[offset+3]<<16)&0xFF0000) + ((buffer[offset+4]<<24)&0xFF000000)
	offset+=2
      #print "ILV command Length = ", str(longitud)
      status = 0xFF
      if longitud>0:
        status = buffer[offset+3]
      if code == 0x71: # "Asynchronous Message" Command
        if status != ILV_OK:
	  return {'status':'Error', 'data':'Erroneous asyncronous message'}
        self.ILVCommand = code;
        if longitud>6:
          return self.processILV(buffer, size, offset+4)
      #print "code:", str(code)
      # Execute when ILVCommand already loaded on previous iteration
      if self.ILVCommand == 0x71: # Asynchronous message
        self.ILVCommand = code;
        if   code == 0x01: # Control message
          pass
        elif code == 0x02: # Asynchronous image message
          return {'status':'huella', 'data': self.processImage(buffer, offset)}
	else:
          print "Unknown asynchronous message"
        return;
      if code == 0x22: # Identification command
        if status != ILV_OK:
          print "Error code %d" % status
	  if status != ILVERR_CMDE_ABORTED:
            print "Biometric device error, please try again"
          return;
        if buffer[offset+4]==ILVSTS_HIT:
          dbIdx = buffer[offset+5]+(buffer[offset+6]<<8)+(buffer[offset+7]<<16)+(buffer[offset+8]<<24)
          print "Identified user"
          ILVCommand = code
          if longitud>6:
            self.processILV(buffer, size, offset+9)
        else:
          print "Unidentified user"
        return
      if code == 0x21: # Enrol command
        ILVCommand = code
        if status != ILV_OK:
          print "Error code %d" % status
          if status != ILVERR_CMDE_ABORTED:
            print "Biometric device error, please try again"
	  return
        if buffer[offset+4]==ILVSTS_OK:
          dbIdx = buffer[offset+5]+(buffer[offset+6]<<8)+(buffer[offset+7]<<16)+(buffer[offset+8]<<24)
          #print "User correctly enrolled"
          ILVCommand = code
          if longitud>6:
            return self.processILV(buffer, size, offset+9)
        else:
          print "User not enrolled, please try again"
	return
      if code == 0x3d: # Image command
        ILVCommand = code
        #print "Final fingerprint received"
        return {'status':'huellaf', 'data': self.processImage(buffer, offset)}
  '''
				
/*				if(status != ILV_OK){
					print "Codigo de respuesta: "+Integer.toHexString(0xFF & status);
					if(status != ILVERR_CMDE_ABORTED)mostrarMensaje("Error del dispositivo biometrico, intente de nuevo");
					return;
				}
				if(buffer[offset+4]==ILVSTS_OK){
					int dbIdx = buffer[offset+5]+(buffer[offset+6]<<8)+(buffer[offset+7]<<16)+(buffer[offset+8]<<24);
					print "Usuario enrolado correctamente");
					ILVCommand = code;
					if(longitud>6)processILV(buffer, size, offset+9);
				}else{
					hRefresh.sendEmptyMessage(GUI_ENROL_FREE_ERROR);
					print "Usuario No enrolado");
					mostrarMensaje("No enrolado, intente nuevamente");
//					mostrarResultadoHuella(false,"");
				}
*/
				return;
			}
			if(code == 0x04){ // ID de usuario
				int userID=0; //Los Ids los manejare numericos
				for(int i=(int)longitud; i>0; i--){
					userID=(userID<<8)+(((short)buffer[offset+2+i])&0xFF);
				}

				if(runningOP == OP_ENROLAR){
					if(userID == 50649){ //TODO: arreglar QD
						hRefresh.sendEmptyMessage(GUI_ADMIN_FREE);
						adminLoged = true;
					}else{
						mostrarMensaje("Usuario sin privilegios");
						hRefresh.sendEmptyMessage(GUI_MAIN_FREE);
						return;
					}
				}else{
			        try{
			        	RespuestaSiNo respuesta = servicio.llamarServicioSiNo("registrarEvento", params);
			        	print "Respuesta registro evento: " + respuesta.respuesta);
			        }catch (Exception e) {
						// TODO: handle exception
					}
				}
				mostrarResultadoHuella(true,""+userID);
				print userID +" identificado correctamente";
//				mostrarMensaje(userID +" identificado correctamente");
				return;
			}
		}
	}
  '''
  def processImage(self, buffer, offset):
    headerSize		= buffer[offset+4]; # Must be 0x0A
    rowNumber		= (buffer[offset+5]&0xFF) + ((buffer[offset+6]<<8)&0xFF00)
    colNumber		= (buffer[offset+7]&0xFF) + ((buffer[offset+8]<<8)&0xFF00)
    vertRes		= (buffer[offset+9]&0xFF) + ((buffer[offset+10]<<8)&0xFF00)
    horzRes		= (buffer[offset+11]&0xFF) + ((buffer[offset+12]<<8)&0xFF00)
    compression		= buffer[offset+13]
    compressionParam 	= buffer[offset+14]
    imgSize		= rowNumber*colNumber
    offset+=15
#    print "----Image data---- \nrowNumber: %d \ncolNumber: %d \nvertRes: %d \nhorzRes: %d \n%d \n%d" % (rowNumber, colNumber, vertRes, horzRes, compression, compressionParam)
    huella = buffer[offset:offset+imgSize].tostring()
    return {'rowNumber':rowNumber, 'colNumber':colNumber, 'huella':huella}

  #Misc / closing
  def exit_handler(self):
    self.close()

  def close(self):
    if hasattr(self, 'readThread'):
      print "Ending read Thread"
      self.readThread.do_run = False
      self.readThread.join()
      del(self.readThread)
    usb.util.dispose_resources(self.lector)

def searchTerminal():
  found = []
  for terminal in knownMorphoTerminals:
    if 'vendID' in terminal:
      vendID = terminal['vendID']
    else:
      vendID = def_vendID
      terminal['vendID'] = def_vendID
    print "Searching %s : %d"% (terminal['name'], vendID) 
    dev = usb.core.find(idVendor=vendID, idProduct=terminal['prodID'])
    if dev is not None:
      print "Found", terminal['name']
      found.append([dev,terminal])
  return found

def paramsFromFound(data):
  if 'baudrate' in data:
    baudrate = data['baudrate']
  else:
    baudrate = def_baudrate
  if 'endPOut' in data:
    endPOut = data['endPOut']
  else:
    endPOut = def_endPOut
  if 'endPIn' in data:
    endPIn  = data['endPIn']  
  else:
    endPIn  = def_endPIn  
  return baudrate, endPOut, endPIn  

# Helpers
def int2array(i):
  return [i >> n & 0xff for n in (0,8,16,24)]

def short2array(i):
  return [i >> n & 0xff for n in (0,8)]
