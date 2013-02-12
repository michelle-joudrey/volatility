# Volatility
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

"""
@author:       Andrew Case
@license:      GNU General Public License 2.0 or later
@contact:      atcuno@gmail.com
@organization: Digital Forensics Solutions
"""

import volatility.obj as obj
import volatility.plugins.linux.flags as linux_flags
import volatility.plugins.linux.common as linux_common
import volatility.plugins.linux.pslist as linux_pslist

class linux_proc_maps(linux_pslist.linux_pslist):
    """Gathers process maps for linux"""

    def calculate(self):
        linux_common.set_plugin_members(self)
        tasks = linux_pslist.linux_pslist.calculate(self)

        for task in tasks:
            if task.mm:
                for vma in task.get_proc_maps():
                    yield task, vma            

    def render_text(self, outfd, data):
        self.table_header(outfd, [("Start", "[addrpad]"),
                                  ("End",   "[addrpad]"),
                                  ("Flags", "6"),
                                  ("Pgoff", "[addr]"),
                                  ("Major", "6"),
                                  ("Minor", "6"),
                                  ("Inode", "10"),
                                  ("File Path", "80"),                    
                                 ]) 
        for task, vma in data:

            mm = task.mm

            if vma.vm_file:
                inode = vma.vm_file.dentry.d_inode
                major, minor = inode.i_sb.major, inode.i_sb.minor
                ino = inode.i_ino
                pgoff = vma.vm_pgoff << 12
                fname = linux_common.get_path(task, vma.vm_file)
            else:
                (major, minor, ino, pgoff) = [0] * 4

                if vma.vm_start <= mm.start_brk and vma.vm_end >= mm.brk:
                    fname = "[heap]"

                elif vma.vm_start <= mm.start_stack and vma.vm_end >= mm.start_stack:
                    fname = "[stack]"

                else:
                    fname = ""

            self.table_row(outfd,
                vma.vm_start,
                vma.vm_end,
                str(vma.vm_flags),
                pgoff,
                major,
                minor,
                ino,
                fname)