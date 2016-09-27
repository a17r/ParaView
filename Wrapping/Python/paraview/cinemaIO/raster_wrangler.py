#==============================================================================
# Copyright (c) 2015,  Kitware Inc., Los Alamos National Laboratory
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this
# list of conditions and the following disclaimer in the documentation and/or other
# materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may
# be used to endorse or promote products derived from this software without specific
# prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#==============================================================================
"""
    Module that uses one of the available back end libraries to write out image
    files for cinema's file store class.
"""

import numpy
import os
import warnings

exrEnabled = False
try:
    import OexrHelper as exr
    exrEnabled = True
    print "Imported OpenEXR, will default to *.exr for float images (z-buffer, \
    value, etc.)."
except ImportError:
    pass

pilEnabled = False
try:
    import PIL.Image
    import PIL.ImImagePlugin
    pilEnabled = True
except ImportError:
    pass

vtkEnabled = False
try:
    import sys
    if "paraview" in sys.modules:
        import paraview.vtk
        import paraview.vtk.vtkIOImage
        from paraview.vtk.vtkIOImage import (vtkPNGReader,
                                             vtkBMPReader,
                                             vtkPNMReader,
                                             vtkTIFFReader,
                                             vtkJPEGReader,
                                             vtkPNGWriter,
                                             vtkBMPWriter,
                                             vtkPNMWriter,
                                             vtkTIFFWriter,
                                             vtkJPEGWriter)
        from paraview.vtk.vtkCommonDataModel import vtkImageData
        from paraview import numpy_support as n2v
    else:
        import vtk
        from vtk import (vtkPNGReader,
                         vtkBMPReader,
                         vtkPNMReader,
                         vtkTIFFReader,
                         vtkJPEGReader,
                         vtkPNGWriter,
                         vtkBMPWriter,
                         vtkPNMWriter,
                         vtkTIFFWriter,
                         vtkJPEGWriter,
                         vtkImageData)
        from vtk.util import numpy_support as n2v
    vtkEnabled = True
except ImportError:
    pass

class RasterWrangler(object):
    """
    Isolates the specifics of raster file formats from the cinema store.
    In particular this delegates the task to one or more subsidiary modules.
    The choice of which is open to facilitate packaging in different
    places, i.e. PIL for desktop and small packages, VTK for HPC contexts.
    """
    def __init__(self):
        self.backends = set()
        if exrEnabled:
            self.backends.add("OpenEXR")
        elif pilEnabled:
            self.backends.add("PIL")
        elif vtkEnabled:
            self.backends.add("VTK")
        self.compress = True

    def enableOpenEXR(self):
        """Try to turn on OpenEXR file IO support"""
        if exrEnabled:
            self.backends.add("OpenEXR")
        else:
            warnings.warn("OpenEXR module not found", ImportWarning)

    def enablePIL(self):
        """Try to turn on PIL file IO support"""
        if pilEnabled:
            self.backends.add("PIL")
        else:
            warnings.warn("PIL module not found", ImportWarning)

    def enableVTK(self):
        """Try to turn on VTK file IO support"""
        if vtkEnabled:
            self.backends.add("VTK")
        else:
            warnings.warn("VTK module not found", ImportWarning)

    def _make_writer(self,filename):
        "Internal function."
        extension = None
        parts = filename.split('.')
        if len(parts) > 1:
            extension = parts[-1]
        else:
            raise RuntimeError, "Filename has no extension, cannot guess writer to use"

        if extension == 'png':
            return vtkPNGWriter()
        elif extension == 'bmp':
            return vtkBMPWriter()
        elif extension == 'ppm':
            return vtkPNMWriter()
        elif extension == 'tif' or extension == 'tiff':
            return vtkTIFFWriter()
        elif extension == 'jpg' or extension == 'jpeg':
            return vtkJPEGWriter()
        elif extension == 'vti':
            return vtkXMLImageDataWriter()
        else:
            raise RuntimeError, "Cannot infer filetype from extension:", extension

    def _make_reader(self,filename):
        "Internal function."
        extension = None
        parts = filename.split('.')
        if len(parts) > 1:
            extension = parts[-1]
        else:
            raise RuntimeError, "Filename has no extension, please guess reader to use"

        if extension == 'png':
            return vtkPNGReader()
        elif extension == 'bmp':
            return vtkBMPReader()
        elif extension == 'ppm':
            return vtkPNMReader()
        elif extension == 'tif' or extension == 'tiff':
            return vtkTIFFReader()
        elif extension == 'jpg' or extension == 'jpeg':
            return vtkJPEGReader()
        elif extension == 'vti':
            return vtkXMLImageDataReader()
        else:
            raise RuntimeError, "Cannot infer filetype from extension:", extension

    def genericreader(self, fname):
        """read generic binary data dump"""
        with open(fname, "r") as file:
            return file.read()

    def genericwriter(self, imageslice, fname):
        """write generic binary data dump"""
        with open(fname, "w") as file:
            file.write(imageslice)

    def rgbreader(self, fname):
        """opens a color image file and returns it as a color buffer"""
        if "VTK" in self.backends:
            height = imageslice.shape[1]
            width = imageslice.shape[0]
            contig = imageslice.reshape(height*width,3)
            vtkarray = n2v.numpy_to_vtk(contig)
            id = vtkImageData()
            id.SetExtent(0, height-1, 0, width-1, 0, 0)
            id.GetPointData().SetScalars(vtkarray)

            writer = self._make_writer(fname)
            writer.SetInputData(id)
            writer.SetFileName(fname)
            writer.Write()

        elif "PIL" in self.backends:
            try:
                im = PIL.Image.open(fname)
                #print "read", fname
                return numpy.array(im, numpy.uint8).reshape(im.size[1],im.size[0],3)
            except:
                #print "no such file", fname
                return None

        else:
            print "Warning: need PIL or VTK to read from " + fname

    def rgbwriter(self, imageslice, fname):
        """takes in a color buffer and writes it as an image file"""
        if "VTK" in self.backends:
            height = imageslice.shape[1]
            width = imageslice.shape[0]
            contig = imageslice.reshape(height*width,3)
            vtkarray = n2v.numpy_to_vtk(contig)
            id = vtkImageData()
            id.SetExtent(0, height-1, 0, width-1, 0, 0)
            id.GetPointData().SetScalars(vtkarray)

            writer = self._make_writer(fname)
            writer.SetInputData(id)
            writer.SetFileName(fname)
            writer.Write()

        elif "PIL" in self.backends:
            imageslice = numpy.flipud(imageslice)
            pimg = PIL.Image.fromarray(imageslice)
            pimg.save(fname)

        else:
            print "Warning: need PIL or VTK to write to " + fname

    def valuewriter(self, imageSlice, fname, range):
        """ Takes in either a (1C) float or a RGB (3C) buffer and writes it as
        an image file."""
        dimensions = imageSlice.shape
        if len(dimensions) == 2 and imageSlice.dtype == numpy.float32:
          # Treat as single channel floating point buffer. Adjust the filename.
          #print "->>> imageslice max/min: ", imageSlice.max(), " / ", imageSlice.min()
          baseName, ext = os.path.splitext(fname)
          adjustedName = baseName + self.floatExtension()
          self.zwriter(imageSlice, adjustedName)

        elif (len(dimensions) > 2) and (dimensions[2] == 3):
          # Treat as a RGB buffer

          w0 = numpy.left_shift(imageSlice[:,:,0].astype(numpy.uint32), 16)
          #print "W0", w0.shape, numpy.amin(w0), numpy.amax(w0)
          w1 = numpy.left_shift(imageSlice[:,:,1].astype(numpy.uint32), 8)
          #print "W1", w1.shape, numpy.amin(w1), numpy.amax(w1)
          w2 = imageSlice[:,:,2]
          #print "W2", w2.shape, numpy.amin(w2), numpy.amax(w2)

          value = numpy.bitwise_or(w0,w1)
          value = numpy.bitwise_or(value,w2)
          value = numpy.subtract(value.astype(numpy.int32),1) #0 is reserved as "nothing"
          if range[1] != range[0]:
            normalized_val = numpy.divide(value.astype(float),(0xFFFFFE/(range[1]-range[0])))
          else:
            normalized_val = numpy.divide(value.astype(float),0xFFFFFE)
          adjusted_val = numpy.add(normalized_val,range[0])
          #print "RANGE", range[0], "," , range[1]
          #print "BV", adjusted_val.shape, numpy.amin(adjusted_val), numpy.amax(adjusted_val)

          baseName, ext = os.path.splitext(fname)
          adjustedName = baseName + self.floatExtension()

          self.zwriter(adjusted_val, adjustedName)

        else:
          raise ValueError("Invalid dimensions for a value raster.")

    def valuereader(self, fname):
        """ Opens a value image file and returns it as either a color buffer
        or a floating point array (depending on how the image was exported)."""
        baseName, ext = os.path.splitext(fname)
        if ext == self.floatExtension():
          # Treat as single channel floating point buffer.
          return self.zreader(fname)
        else:
          # Treat as a RGB buffer
          return self.rgbreader(fname)

    def floatExtension(self):
        """determine file extension for depth images"""
        if "OpenEXR" in self.backends:
            return ".exr"

        else:
            return ".im"

    def zreader(self, fname):
        """reads a depth file to make a depth buffer"""
        if not self.compress:
            im = PIL.Image.open(fname)
            return numpy.array(im, numpy.float32).reshape(im.size[1],im.size[0])
        else:
            adjustedName = fname + ".npz"
            file = open(adjustedName, mode='r')
            tz = numpy.load(file)
            imageslice = tz[tz.files[0]]
            tz.close()
            file.close()
            return imageslice

    def zwriter(self, imageslice, fname):
        """takes in a depth buffer and writes it as a depth file"""
        if not self.compress:
            imageslice = numpy.flipud(imageslice)
            pimg = PIL.Image.fromarray(imageslice)
            #TODO:
            # don't let ImImagePlugin.py insert the Name: filename in line two
            # why? because ImImagePlugin.py reader has a 100 character limit
            pimg.save(fname)
        else:
            adjustedName = fname + ".npz"
            file = open(adjustedName, mode='w')
            print adjustedName
            print imageslice.shape, numpy.amin(imageslice), numpy.amax(imageslice)
            numpy.savez_compressed(file, imageslice)
            file.close()

    def assertvalidimage(self, filename):
        """tests that a given file is syntactically correct"""
        if not os.path.isfile(filename):
            raise IOError(filename + " does not exist.")

        if "OpenEXR" in self.backends:
            if not exr.isOpenExrFile(filename):
                raise IOError(filename + " cannot be opened using OpenEXR.")

        elif "VTK" in self.backends:
            reader = self._make_reader(filename)
            if not reader.CanReadFile(filename):
                raise IOError("VTK Cannot open file " + filename)

        elif "PIL" in self.backends:
            try:
                PIL.Image.open(filename)
            except IOError:
                raise

        else:
            raise RuntimeError(
                "Warning: need OpenEXR or PIL or VTK to validate file store")
