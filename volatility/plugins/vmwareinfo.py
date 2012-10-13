# Volatility
# Copyright (C) 2009-2012 Volatile Systems
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details. 
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 
#

import volatility.plugins.crashinfo as crashinfo
import volatility.utils as utils

class VMwareInfo(crashinfo.CrashInfo):
    """Dump VMware VMSS/VMSN information"""
    
    target_as = ['VMWareSnapshotFile']
        
    def render_text(self, outfd, data):
    
        header = data.get_header()
        
        ## First some of the version meta-data
        outfd.write("Magic: {0:#x} (Version {1})\n".format(header.Magic, header.Version))
        outfd.write("Group count: {0:#x}\n".format(header.GroupCount))
        
        ## Now let's print the runs 
        self.table_header(outfd, [("File Offset", "[addrpad]"), 
                                  ("PhysMem Offset", "[addrpad]"),
                                  ("Size", "[addrpad]")])
        
        for memory_offset, file_offset, length in data.get_runs():
            self.table_row(outfd, file_offset, memory_offset, length)
            
        outfd.write("\n")
        
        ## Go through and print the groups and tags
        self.table_header(outfd, [("DataOffset", "[addrpad]"), 
                                  ("DataSize", "[addr]"), 
                                  ("Name", "50"), 
                                  ("Value", "")])
    
        for group in header.Groups:
            for tag in group.Tags:
            
                ## The indices should look like [0][1] 
                indices = ""
                for i in tag.TagIndices:
                    indices += "[{0}]".format(i)
                    
                ## Attempt to format standard values
                if tag.DataMemSize == 0:
                    value = ""
                elif tag.DataMemSize == 1:
                    value = "{0}".format(tag.cast_as("unsigned char"))
                elif tag.DataMemSize == 2:
                    value = "{0}".format(tag.cast_as("unsigned short"))
                elif tag.DataMemSize == 4:
                    value = "{0:#x}".format(tag.cast_as("unsigned int"))
                elif tag.DataMemSize == 8:
                    value = "{0:#x}".format(tag.cast_as("unsigned long long"))
                else:
                    value = ""
                                        
                self.table_row(outfd, 
                               tag.RealDataOffset,
                               tag.DataMemSize, 
                               "{0}/{1}{2}".format(group.Name, tag.Name, indices), 
                               value)
                               
                ## In verbose mode, when we're *not* dealing with memory segments, 
                ## print a hexdump of 
                if (self._config.VERBOSE and tag.DataMemSize > 0 
                        and str(group.Name) != "memory" and value == ""):
                        
                    ## When we read, it must be done via the AS base (FileAddressSpace)
                    addr = tag.RealDataOffset
                    ## FIXME: FileAddressSpace.read doesn't handle NativeType so we have to case. 
                    ## Remove the cast after Issue #350 is fixed. 
                    data = tag.obj_vm.read(addr, int(tag.DataMemSize)) 
                    
                    outfd.write("".join(["{0:#010x}  {1:<48}  {2}\n".format(addr + o, h, ''.join(c))
                                for o, h, c in utils.Hexdump(data)
                                ]))
                     
                    ## If we alter the plugin later to accept an output directory, we can 
                    ## extract the snapshot thumbnail image using the code below. 
                    #if str(group.Name) == "MKSVMX" and str(tag.Name) == "imageData":
                    #    f = open("test.png", "wb")
                    #    f.write(data)
                    #    f.close()
                    
                    