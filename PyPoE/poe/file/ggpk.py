"""
GGPK Toolkit

Overview
-------------------------------------------------------------------------------

+----------+------------------------------------------------------------------+
| Path     | PyPoE/poe/file/ggpk/__init__.py                                  |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                                                             |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
-------------------------------------------------------------------------------

Toolkit for reading & writing GGPK Files. Provides additional utility functions.

Agreement
-------------------------------------------------------------------------------

See PyPoE/LICENSE

TODO
-------------------------------------------------------------------------------

write untested
"""

# =============================================================================
# Imports
# =============================================================================

# Python
import io
import struct
import os
import re

#
from PyPoE.shared import InheritedDocStringsMeta
from PyPoE.shared.decorators import doc
from PyPoE.shared.mixins import ReprMixin
from PyPoE.poe.file.shared import AbstractFileReadOnly, ParserError

# =============================================================================
# Classes
# =============================================================================


class BaseRecord(ReprMixin):
    """
    :ivar _container:
    :type container: GGPKFile

    :ivar length:
    :type length: int

    :ivar offset:
    :type offset: int
    """
    tag = None

    __slots__ = ['_container', 'length', 'offset']

    def __init__(self, container, length, offset):
        self._container = container
        self.length = length
        self.offset = offset

    def read(self, ggpkfile):
        """
        Read this record's header for the given GGPKFile instance.

        :param GGPKFile ggpkfile: GGPKFile instance
        """
        pass

    def write(self, ggpkfile):
        """
        Wriite this record's header for the given GGPKFile instance.

        :param GGPKFile ggpkfile: GGPKFile instance
        """
        ggpkfile.write(struct.pack('<i', self.length))
        ggpkfile.write(self.tag)


class MixinRecord(object):
    def __init__(self, *args, **kwargs):
        super(MixinRecord, self).__init__(*args, **kwargs)
    
    def _get_name(self):
        """
        Returns name of the file.

        :return str: name of the file
        """
        return self._name
    
    def _set_name(self, name):
        """
        Set name of file.
        
        Takes care of adjusting name_length accordingly.
        """
        self._name = name
        # Account for null bytes
        self._name_length = len(name) + 1
        
    name = property(fget=_get_name, fset=_set_name)


@doc(append=BaseRecord)
class GGPKRecord(BaseRecord):
    """
    The GGPKRecord is the master record of the file; it always contains two
    entries. First is the root directory, 2nd is a FreeRecord.
    
    :ivar list[int] offsets: List of offsets for records.
    """
    tag = 'GGPK'

    __slots__ = BaseRecord.__slots__.copy() + ['offsets']

    @doc(doc=BaseRecord.read)
    def read(self, ggpkfile):
        # Should be 2, TODO?
        records = struct.unpack('<i', ggpkfile.read(4))[0]
        self.offsets = []
        for i in range(0, records):
            self.offsets.append(struct.unpack('<q', ggpkfile.read(8))[0])

    @doc(doc=BaseRecord.write)
    def write(self, ggpkfile):
        # Write length & tag
        super(GGPKRecord, self).write(ggpkfile)
        # Should always be 2
        ggpkfile.write(struct.pack('<i', 2))
        for i in range(0, len(offsets)):
            ggpkfile.write(struct.unpack('<q', offsets[i]))


class DirectoryRecordEntry(ReprMixin):
    """
    :ivar int hash: murmur2 32bit hash
    :ivar int offset: offset in GGPKFile
    """
    def __init__(self, hash, offset):
        """
        :param int hash: murmur2 32bit hash
        :param int offset:  ffset in GGPKFile
        """
        self.hash = hash
        self.offset = offset


@doc(append=BaseRecord)
class DirectoryRecord(MixinRecord, BaseRecord):
    """
    Represents a directory in the virtual GGPKFile file tree.

    :ivar str _name: Name of directory
    :ivar int _name_length: Length of name
    :ivar int _entries_length: Number of directory entries
    :ivar int hash: SHA256 hash of file contents
    :ivar list[DirectoryRecordEntry] entries: Directory entries
    """

    tag = 'PDIR'

    __slots__ = BaseRecord.__slots__.copy() + ['_name', '_name_length', 'entries_length', 'hash', 'entries']

    def __init__(self, *args, **kwargs):
        super(DirectoryRecord, self).__init__(*args, **kwargs)

    @doc(doc=BaseRecord.read)
    def read(self, ggpkfile):
        self._name_length = struct.unpack('<i', ggpkfile.read(4))[0]
        self.entries_length = struct.unpack('<i', ggpkfile.read(4))[0]  
        self.hash = int.from_bytes(ggpkfile.read(32), 'big')
        # UTF-16 2-byte width
        self._name = ggpkfile.read(2 * (self._name_length - 1)).decode('UTF-16_LE')
        # Null Termination
        ggpkfile.seek(2, os.SEEK_CUR)
        self.entries = []
        for i in range(0, self.entries_length):
            self.entries.append(DirectoryRecordEntry(
                hash=struct.unpack('<I', ggpkfile.read(4))[0],
                offset=struct.unpack('<q', ggpkfile.read(8))[0],
            ))

    @doc(doc=BaseRecord.write)
    def write(self, ggpkfile):
        # Error Checking & variable preparation
        if len(self.hash) != 32:
            raise ValueError('Hash must be 32 bytes, was %s bytes' % len(self.hash))
        if len(self.entries) != self.entries_length:
            raise ValueError('Numbers of entries must match with length')
        name_str = self._name.encode('UTF-16')
        # Write length & tag
        super(DirectoryRecord, self).write(ggpkfile)
        ggpkfile.write(struct.pack('<i', self._name_length))
        ggpkfile.write(struct.pack('<i', self.entries_length))
        # Fixed 32-bytes
        ggpkfile.write(self.hash)
        ggpkfile.write(name_str)
        ggpkfile.write(struct.pack('<h', 0))
        # TODO: len(self.entries)
        for entry in self.entries:
            ggpkfile.write(struct.pack('<i', entry.hash))
            ggpkfile.write(struct.pack('<q', entry.offset))


@doc(append=BaseRecord)
class FileRecord(MixinRecord, BaseRecord):
    """
    Represents a file in the virtual GGPKFile file tree.

    :ivar str _name: Name of file
    :ivar int _name_length: Length of name
    :ivar int hash: SHA256 hash of file contents
    :ivar int data_start: starting offset of data
    :ivar int data_length: length of data
    """

    tag = 'FILE'

    __slots__ = BaseRecord.__slots__.copy() + ['_name', '_name_length', 'hash', 'data_start', 'data_length']

    def __init__(self, *args, **kwargs):
        super(FileRecord, self).__init__(*args, **kwargs)
        
    def extract(self, buffer=None):
        """
        Extracts this file contents into a memory file object.

        :param buffer: GGPKFile Buffer to use; if None, open the parent GGPKFile
        and use it as buffer.
        :type buffer: io.Bytes or None

        :return: memory file buffer object
        :rtype: io.BytesIO
        """
        if buffer is None:
            return self._container.get_read_buffer(
                self._container._file_path_or_raw,
                self.extract,
            )

        # The buffer object is taken care of in get_read_buffer if it's a file
        buffer.seek(self.data_start)
        memfile = io.BytesIO()
        memfile.write(buffer.read(self.data_length))
        # Set the pointer to the beginning
        memfile.seek(0)
        return memfile

    def extract_to(self, directory, name=None):
        """
        Extracts the file to the given directory.
        
        :param str directory: the directory to extract the file to
        :param name: the name of the file; if None use the file name as in the record.
        :type name: str or None
        """
        name = self._name if name is None else name 
        path = os.path.join(directory, name)
        with open(path, 'bw') as exfile:
            # TODO Mem leak?
            exfile.write(self.extract().read())

    @doc(doc=BaseRecord.read)
    def read(self, ggpkfile):
        self._name_length = struct.unpack('<i', ggpkfile.read(4))[0]
        self.hash = int.from_bytes(ggpkfile.read(32), 'big')
        # UTF-16 2-byte width
        self._name = ggpkfile.read(2 * (self._name_length - 1)).decode('UTF-16')
        # Null Termination
        ggpkfile.seek(2, os.SEEK_CUR)
        self.data_start = ggpkfile.tell()
        # Length 4B - Tag 4B - STRLen 4B - Hash 32B + STR ?B  
        self.data_length = self.length - 44 - self._name_length * 2
        
        ggpkfile.seek(self.data_length, os.SEEK_CUR)

    @doc(doc=BaseRecord.write)
    def write(self, ggpkfile):
        # Error checking & variable preparation first
        if len(self.hash) != 32:
            raise ValueError('Hash must be 32 bytes, was %s bytes' % len(self.hash))
        
        name_str = self._name.encode('UTF-16')
        # Write length & tag
        super(FileRecord, self).write(ggpkfile)
        ggpkfile.write(struct.pack('<i', self._name_length))
        # Fixed 32-bytes
        ggpkfile.write(self.hash)
        ggpkfile.write(name_str)
        ggpkfile.write(struct.pack('<h', 0))
        
        #TODO: Write File Contents here?


@doc(append=BaseRecord)
class FreeRecord(BaseRecord):
    """
    :param int next_free: offset of next free record
    """
    tag = 'FREE'

    __slots__ = BaseRecord.__slots__.copy() + ['next_free']

    @doc(doc=BaseRecord.read)
    def read(self, ggpkfile):
        self.next_free = struct.unpack('<q', ggpkfile.read(8))[0]
        ggpkfile.seek(self.length -16, os.SEEK_CUR)

    @doc(doc=BaseRecord.write)
    def write(self, ggpkfile):
        # Write length & tag
        super(FreeRecord, self).write(ggpkfile)
        ggpkfile.write(struct.pack('<q', self.next_free))


class DirectoryNode(object):
    """
    :ivar children:
    :type children: list[DirectoryNode]

    :ivar parent:
    :type parent: DirectoryNode

    :ivar record:
    :type record: DirectoryRecord or FileRecord

    :ivar hash:
    :type hash: str
    """

    __slots__ = ['children', 'parent', 'record', 'hash']

    def __init__(self, record, hash, parent):
        self.children = []
        self.parent = parent
        self.record = record
        self.hash = hash

    def __getitem__(self, item):
        """
        Return the the specified file or directory path.

        The path will accept valid paths for the current operating system,
        however I suggest using forward slashes ( / ) as they are supported on
        both Windows and Linux.

        Since the each node supports the same syntax, all these calls are
        equivalent:
        - self['directory1']['directory2']['file.ext']
        - self['directory1']['directory2/file.ext']
        - self['directory1/directory2']['file.ext']
        - self['directory1/directory2/file.ext']

        :param item: file or directory path
        :type item: str

        :return: returns the DirectoryNode of the specified item if found, None
        otherwise
        :rtype: DirectoryNode or None
        """
        path = []
        while item:
            item, result = os.path.split(item)
            path.insert(0, result)

        obj = self
        while True:
            try:
                item = path.pop(0)
            except IndexError:
                return obj

            for child in obj.children:
                if child.name == item:
                    obj = child
                    break
            else:
                return None

    @property
    def directories(self):
        """
        Returns a list of directories with a file record.

        :return:
        :rtype: list[DirectoryRecord]
        """
        return [node for node in self.children if isinstance(node.record, DirectoryRecord)]

    @property
    def files(self):
        """
        Returns a list of nodes with a file record.

        :return:
        :rtype: list[FileRecord]
        """
        return [node for node in self.children if isinstance(node.record, FileRecord)]
        
    def _get_name(self):
        """
        Returns the name associated with the stored record.

        :return: name of the file/directory
        :rtype: str
        """
        return self.record.name if self.record.name else 'ROOT'
        
    name = property(_get_name)

    def search(self, regex, search_files=True, search_directories=True):
        """

        :param regex: compiled regular expression to use
        :type regex: re.compile()

        :param search_files: Whether FileRecords should be searched
        :type search_files: bool

        :param search_directories: Whether DirectoryRecords should be searched
        :type search_directories: bool

        :return: List of matching nodes
        :rtype: list containing DirectoryNode
        """
        if isinstance(regex, str):
            regex = re.compile(regex)

        nodes = []

        #func = lambda n: nodes.append(n) if re.search(regex, n.name) else None
        #self.walk(func)

        q = []
        q.append(self)

        while len(q) > 0:
            node = q.pop()
            if ((search_files and isinstance(node.record, FileRecord) or
                search_directories and isinstance(node.record, DirectoryRecord))
                    and re.search(regex, node.name)):
                nodes.append(node)

            for child in node.children:
                q.append(child)

        return nodes

    def get_parent(self, n=-1, stop_at=None, make_list=False):
        """
        Gets the n-th parent or returns root parent if at top level.
        Negative values for n will iterate until the root is found.

        If the make_list keyword is set to True, a list of Nodes in the
        following form will be returned:
        [n-th parent, (n-1)-th parent, ..., self]

        :param n: Up to which depth to go to.
        :type n: int

        :param stop_at: DirectoryNode instance to stop the iteration at
        :type stop_at: DirectoryNode or None

        :param make_list: Return a list of nodes instead of parent
        :type make_list: bool

        :return: Returns parent or root node
        :rtype: DirectoryNode
        """
        nodes = []
        node = self
        while (n != 0):
            if node.parent is None:
                break

            if node is stop_at:
                break

            if make_list:
                nodes.insert(0, node)
            node = node.parent
            n -= 1

        return nodes if make_list else node

    def walk(self, function):
        """
        TODO: function = None -> generator like os.walk (dir, [dirs], [files])

        Walks over the nodes and it's sub nodes and executes the specified
        function.
        The function should one argument which will be a dict containing the
        following:
        node - DirectoryNode
        depth - Depth

        :param function: function to call when walking
        :type: callable
        """

        q = []
        q.append({'node': self, 'depth': 0})

        while len(q) > 0:
            data = q.pop()
            function(data)
            for child in data['node'].children:
                q.append({'node': child, 'depth': data['depth']+1})

        """for child in self.children:
            function(child)
            child.walk(function)"""
        
    def extract_to(self, target_directory):
        """
        Extracts the node and its contents (including sub-directories) to the
        specified target directory.
        
        :param target_directory: Path to directory where to extract to.
        :type target_directory: str
        """
        if isinstance(self.record, DirectoryRecord):
            dir_path = os.path.join(target_directory, self.name)
            if not os.path.exists(dir_path):
                os.mkdir(dir_path)

            for node in self.children:
                if isinstance(node.record, FileRecord):
                    node.record.extract_to(dir_path)
                elif isinstance(node.record, DirectoryRecord):
                    node.extract_to(dir_path)
        else:
            self.record.extract_to(target_directory)
        

class GGPKFile(AbstractFileReadOnly, metaclass=InheritedDocStringsMeta):
    """

    :ivar directory:
    :type directory: DirectoryNode

    :ivar file_path:
    :type file_path: str
    """

    def __init__(self, *args, **kwargs):
        AbstractFileReadOnly.__init__(self, *args, **kwargs)
        self.directory = None
        self.records = {}

    def __getitem__(self, item):
        """

        :param item:

        :return:
        :rtype: DirectoryNode
        """
        if self.directory is None:
            raise ValueError('Directory not build')
        if item == 'ROOT':
            return self.directory

        return self.directory[item]

    #
    # Properties
    #

    def _is_parsed(self):
        """

        :return:
        :rtype: bool
        """
        return self.directory is not None

    is_parsed = property(fget=_is_parsed)

    #
    # Private
    #

    def _read_record(self, records, ggpkfile, offset):
        length = struct.unpack('<i', ggpkfile.read(4))[0]
        tag = ggpkfile.read(4).decode('ascii')
        
        '''for recordcls in recordsc:
            if recordcls.tag == tag:
                break

        record = recordcls(self, length, offset)'''

        if tag == 'FILE':
            record = FileRecord(self, length, offset)
        elif tag == 'FREE':
            record = FreeRecord(self, length, offset)
        elif tag == 'PDIR':
            record = DirectoryRecord(self, length, offset)
        elif tag == 'GGPK':
            record = GGPKRecord(self, length, offset)
        else:
            raise ValueError()

        record.read(ggpkfile)
        records[offset] = record
    
    def directory_build(self, parent=None):
        """
        Rebuilds the directory or directory node. 
        If the root directory is rebuild it will be stored in the directory
        object variable.
        
        :param parent: parent DirectoryNode. If None generate the root directory
        :type parent: DirectorNode or None

        :return: Returns the parent node or the root node if parent was None
        :rtype: DirectoryNode

        :raises ParserError: if performed without calling .read() first
        :raises ParserError: if offsets pointing to records types which are not
        FileRecord or DirectoryRecord
        """
        if not self.records:
            raise ParserError('No records - perform .read() first')

        # Build Root directory
        if parent is None:
            ggpkrecord = self.records[0]
            for offset in ggpkrecord.offsets:
                record = self.records[offset]
                if isinstance(record, DirectoryRecord):
                    break
            if not isinstance(record, DirectoryRecord):
                raise ParserError('GGPKRecord does not contain a DirectoryRecord,\
                    got %s' % type(record))

            root = DirectoryNode(record, None, None)

            self.directory = root
        else:
            root = parent

        l = []
        for entry in root.record.entries:
            l.append((entry.offset, entry.hash, root))

        try:
            while True:
                offset, hash, parent = l.pop()
                record = self.records[offset]
                node = DirectoryNode(record, hash, parent)
                parent.children.append(node)

                if isinstance(record, DirectoryRecord):
                    for entry in record.entries:
                        l.append((entry.offset, entry.hash, node))
        except IndexError:
            pass

        return root
        
    def _read(self, buffer, *args, **kwargs):
        """
        Reads the records from the file into object.records.
        """
        records = {}
        offset = 0
        size = buffer.seek(0, os.SEEK_END)

        # Reset Pointer
        buffer.seek(0, os.SEEK_SET)

        while offset < size:
            self._read_record(
                records=records,
                ggpkfile=buffer,
                offset=offset,
            )
            offset = buffer.tell()
        self.records = records

    def read(self, file_path_or_raw, *args, **kwargs):
        super(GGPKFile, self).read(file_path_or_raw, *args, **kwargs)
        self._file_path_or_raw = file_path_or_raw


if __name__ == '__main__':
    import cProfile
    from line_profiler import LineProfiler
    profiler = LineProfiler()
    '''profiler.add_function(GGPKFile.read)
    profiler.add_function(GGPKFile._read_record)
    for record in recordsc:
        profiler.add_function(record.read)'''

    ggpk = GGPKFile()
    ggpk.read(r'C:\Games\Path of Exile\Content.ggpk')
    ggpk.directory_build()
    ggpk['Metadata/Items/Rings/AbstractRing.ot'].extract_to('C:/')
    #profiler.run("ggpk.read()")

    #profiler.add_function(GGPKFile.directory_build)
    #profiler.add_function(DirectoryNode.__init__)
    #profiler.run("ggpk.directory_build()")
    #ggpk.directory.directories[2].extract_to('N:/')
    profiler.print_stats()