# Volatility
# Copyright (C) 2007,2008 Volatile Systems
#
# Original Source:
# Copyright (C) 2004,2005,2006 4tphi Research
# Author: {npetroni,awalters}@4tphi.net (Nick Petroni and AAron Walters)
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

"""
@author:       AAron Walters
@license:      GNU General Public License 2.0 or later
@contact:      awalters@volatilesystems.com
@organization: Volatile Systems

   Alias for all address spaces

"""
from volatility import registry
from volatility import utils


class BaseAddressSpace(object):
    """ This is the base class of all Address Spaces. """

    __metaclass__ = registry.MetaclassRegistry
    __abstract = True

    order = 10

    # This can be used to name the address space (e.g. process if etc).
    name = ""

    def __init__(self, base=None, session=None, write=False, profile=None,
                 **kwargs):
        """Base is the AS we will be stacking on top of, opts are options which
        we may use.

        Args:
          base: A base address space to stack on top of (i.e. delegate to it for
            satisfying read requests).

          session: An optional session object.

          write: Should writing be allowed? Not currently implemented.

          profile: An optional profile to use for parsing the address space
            (e.g. needed for hibernation, crash etc.)
        """
        self.base = base
        self.profile = profile
        self.session = session
        self.writeable = (self.session and self.session.writable_address_space or
                          write)

        # This is a short lived cache. If we use a static image, this cache need
        # not expire, however, when analysing a live system we need to flush the
        # cache frequently.
        self.cache = utils.AgeBasedCache(max_age=20)

    def as_assert(self, assertion, error = None):
        """Duplicate for the assert command (so that optimizations don't disable
        them)

        It had to be called as_assert, since assert is a keyword
        """
        if not assertion:
            raise ASAssertionError(error or
                                   "Instantiation failed for unspecified reason")

    def read(self, addr, length):
        """ Read some date from a certain offset """

    def zread(self, addr, length):
        data = self.read(int(addr), int(length))
        if not data:
            return "\x00" * length

        if len(data) < length:
            data += "\x00" * (length - len(data))

        return data

    def get_available_addresses(self):
        """Generates of address ranges as (offset, size) for by this AS."""
        return []

    def get_address_ranges(self, start=0, end=None):
        """Generates the address ranges which fall between start and end.

        Note that start and end are here specified in the virtual address
        space. More importantly this does not say anything about the pages in
        the physical address space - just because pages in the virtual address
        space are contiguous does not mean they are also contiguous in the
        physical address space.
        """
        if end is None:
            end = 0xfffffffffffff

        for offset, length in self._get_address_ranges():
            # The entire range is below what is required - ignore it.
            if offset + length < start:
                continue

            # The range starts after the address we care about - we are done.
            if offset > end:
                return

            # Clip the bottom of the range to the start point, and the end of
            # the range to the end point.
            range_start = max(start, offset)
            range_end = min(end, offset + length)

            if range_end > range_start:
                yield range_start, range_end - range_start

    def _get_address_ranges(self):
        """Generates merged address ranges from get_available_addresses()."""
        try:
            return self.cache.Get("Ranges")
        except KeyError:
            pass

        result = []
        contiguous_voffset = 0
        contiguous_poffset = 0
        total_length = 0
        for (voffset, length) in self.get_available_addresses():
            # Try to join up adjacent pages as much as possible.
            if (voffset == contiguous_voffset + total_length and
                self.vtop(voffset) == contiguous_poffset + total_length):
                total_length += length
            else:
                result.append((contiguous_voffset, total_length))

                # Reset the contiguous range.
                contiguous_voffset = voffset
                contiguous_poffset = self.vtop(voffset)
                total_length = length

        if total_length > 0:
            result.append((contiguous_voffset, total_length))

        # Sort in virtual addresses.
        result.sort()
        self.cache.Put("Ranges", result)
        return result

    def is_valid_address(self, _addr):
        """ Tell us if the address is valid """
        return True

    def write(self, _addr, _buf):
        raise NotImplementedError("Write support for this type of Address Space"
                                  " has not been implemented")

    def vtop(self, addr):
        """Return the physical address of this virtual address."""
        # For physical address spaces, this is a noop.
        return addr

    @classmethod
    def metadata(cls, name, default=None):
        """Obtain metadata about this address space."""
        prefix = '_md_'
        return getattr(cls, prefix + name, default)

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return "<%s @ %#x %s>" % (self.__class__.__name__, hash(self), self.name)


class DummyAddressSpace(BaseAddressSpace):
    """An AS which always returns nulls."""
    __name = 'dummy'
    __abstract = True

    def is_valid_address(self, _offset):
        return True

    def read(self, _offset, length):
        return '0x00' * length


class AbstractVirtualAddressSpace(BaseAddressSpace):
    """Base Ancestor for all Virtual address spaces, as determined by astype"""
    __abstract = True

    def __init__(self, astype = 'virtual', **kwargs):
        super(AbstractVirtualAddressSpace, self).__init__(**kwargs)
        self.astype = astype

        self.as_assert(self.astype == 'virtual' or self.astype == 'any',
                       "User requested non-virtual AS")

    def vtop(self, vaddr):
        raise NotImplementedError("This is a virtual class and should not be "
                                  "referenced directly")


## This is a specialised AS for use internally - Its used to provide
## transparent support for a string buffer so types can be
## instantiated off the buffer.
class BufferAddressSpace(BaseAddressSpace):
    __abstract = True

    def __init__(self, base_offset = 0, data = '', **kwargs):
        self.fname = "Buffer"
        self.data = data
        self.base_offset = base_offset

    def assign_buffer(self, data, base_offset = 0):
        self.base_offset = base_offset
        self.data = data

    def is_valid_address(self, addr):
        return not (addr < self.base_offset or addr > self.base_offset +
                    len(self.data))

    def read(self, addr, length):
        offset = addr - self.base_offset
        return self.data[offset: offset + length]

    def write(self, addr, data):
        self.data = self.data[:addr] + data + self.data[addr + len(data):]
        return True

    def get_available_addresses(self):
        yield (self.base_offset, len(self.data))


class CachingAddressSpace(BaseAddressSpace):
    __abstract = True

    # The size of chunks we cache. This should be large enough to make file
    # reads efficient.
    CHUNK_SIZE = 10 * 1024 * 1024
    CACHE_SIZE = 20

    def __init__(self, **kwargs):
        super(CachingAddressSpace, self).__init__(**kwargs)
        self._cache = utils.FastStore(self.CACHE_SIZE)

    def read(self, addr, length):
        result = ""
        while length > 0:
            data = self.read_partial(addr, length)
            if not data: break

            result += data
            length -= len(data)
            addr += len(data)

        return result

    def zread(self, addr, length):
        return self.read(addr, length)

    def read_partial(self, addr, length):
        chunk_number = addr / self.CHUNK_SIZE
        chunk_offset = addr % self.CHUNK_SIZE
        available_length = min(length, self.CHUNK_SIZE - chunk_offset)

        try:
            data = self._cache.Get(chunk_number)
        except KeyError:
            data = self.base.read(chunk_number * self.CHUNK_SIZE, self.CHUNK_SIZE)
            self._cache.Put(chunk_number, data)

        return data[chunk_offset:chunk_offset+available_length]

    def get_available_addresses(self):
        return self.base.get_available_addresses()


class PagedReader(BaseAddressSpace):
    """An address space which reads in page size.

    This automatically takes care of splitting a large read into smaller reads.
    """
    PAGE_SIZE = 0x1000
    __abstract = True

    def _read_chunk(self, vaddr, length, pad=False):
        """
        Read bytes from a virtual address.

        Args:
          vaddr: A virtual address to read from.
          length: The number of bytes to read.
          pad: If set, pad unavailable data with nulls.

        Returns:
          As many bytes as can be read within this page, or a NoneObject() if we
          are not padding and the address is invalid.
        """
        to_read = min(length, self.PAGE_SIZE - (vaddr % self.PAGE_SIZE))
        paddr = self.vtop(vaddr)
        if paddr is None:
            if pad:
                return "\x00" * to_read
            else:
                return None

        return self.base.read(paddr, to_read)

    def _read_bytes(self, vaddr, length, pad):
        """
        Read 'length' bytes from the virtual address 'vaddr'.
        The 'pad' parameter controls whether unavailable bytes
        are padded with zeros.
        """
        vaddr, length = int(vaddr), int(length)

        result = ''

        while length > 0:
            buf = self._read_chunk(vaddr, length, pad=pad)
            if not buf: break

            result += buf
            vaddr += len(buf)
            length -= len(buf)

        return result

    def read(self, vaddr, length):
        '''
        Read and return 'length' bytes from the virtual address 'vaddr'.
        If any part of that block is unavailable, return None.
        '''
        return self._read_bytes(vaddr, length, pad = False)

    def zread(self, vaddr, length):
        '''
        Read and return 'length' bytes from the virtual address 'vaddr'.
        If any part of that block is unavailable, pad it with zeros.
        '''
        return self._read_bytes(vaddr, length, pad = True)

    def is_valid_address(self, addr):
        vaddr = self.vtop(addr)
        return self.base.is_valid_address(vaddr)

    def get_available_addresses(self):
        for start, length in self.get_available_pages():
            yield start * self.PAGE_SIZE, length * self.PAGE_SIZE


class RunBasedAddressSpace(PagedReader):
    """An address space which uses a list of runs to specify a mapping."""

    # This is a list of (memory_offset, file_offset, length) tuples.
    runs = []
    __abstract = True

    def _read_chunk(self, addr, length, pad):
        file_offset, available_length = self._get_available_buffer(addr, length)

        # Mapping not valid.
        if file_offset is None:
            return "\x00" * available_length

        else:
            return self.base.read(file_offset, min(length, available_length))

    def vtop(self, addr):
        file_offset, _ = self._get_available_buffer(addr, 1)
        return file_offset

    def get_available_pages(self):
        for page_offset, _, page_count in self.runs:
            yield page_offset, page_count

    def _get_available_buffer(self, addr, length):
        """Resolves the address into the file offset.

        This function finds the run that contains this page and returns the file
        address where this page can be found.

        Returns:
          A tuple of (physical_offset, available_length). The physical_offset
          can be None to signify that the address is not valid.
        """
        for virt_addr, file_address, length in self.runs:
            if addr < virt_addr:
                available_length = min(length, virt_addr - addr)
                return (None, available_length)

            # The required page is inside this run.
            if addr >= virt_addr and addr < virt_addr + length:
                file_offset = file_address + (addr - virt_addr)
                available_length = virt_addr + length - addr

                # Offset of page in the run.
                return (file_offset, available_length)

        return None, 0

    def is_valid_address(self, addr):
        return self.vtop(addr) is not None

    def get_available_addresses(self):
        for start, _, length in self.runs:
            yield start, length



class Error(Exception):
    """Address space errors."""


class ASAssertionError(Error):
    """The address space failed to instantiate."""


class AddrSpaceError(Error):
    """Address Space Exception.

    This exception is raised when an AS decides to not be instantiated. It is
    used in the voting algorithm.
    """

    def __init__(self):
        self.reasons = []
        Error.__init__(self, "No suitable address space mapping found")

    def append_reason(self, driver, reason):
        self.reasons.append((driver, reason))

    def __str__(self):
        result = Error.__str__(self) + "\nTried to open image as:\n"
        for k, v in self.reasons:
            result += " {0}: {1}\n".format(k, v)

        return result
