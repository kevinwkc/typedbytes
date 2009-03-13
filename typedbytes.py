def classes():

    from cPickle import dumps, loads, UnpicklingError, HIGHEST_PROTOCOL
    from struct import pack, unpack, error as StructError
    from types import BooleanType, IntType, LongType, FloatType 
    from types import UnicodeType, StringType, TupleType, ListType, DictType

    # Typed bytes types:
    BYTES = 0
    BYTE = 1
    BOOL = 2
    INT = 3
    LONG = 4
    FLOAT = 5
    DOUBLE = 6
    STRING = 7
    VECTOR = 8
    LIST = 9
    MAP = 10

    # Application-specific types:
    PICKLE = 100
    BYTESTRING = 101

    # Low-level types:
    MARKER = 255

    LIST_CODE, MARKER_CODE = (pack('!B', i) for i in (LIST, MARKER))
    UNICODE_ENCODING = 'utf8'

    _len = len

    class Input(object):

        def __init__(self, file, unicode_errors='strict'):
            self.file = file
            self.unicode_errors = unicode_errors
            self.eof = False
            self.handler_table = self.make_handler_table()

        def _read(self):
            try:
                t = unpack('!B', self.file.read(1))[0]
            except StructError:
                self.eof = True
                raise StopIteration
            return self.handler_table[t](self)

        def read(self):
            try:
                return self._read()
            except StopIteration:
                return None

        def _reads(self):
            r = self._read
            while 1:
                yield r()

        __iter__ = reads = _reads

        def close(self):
            self.file.close()

        def read_bytes(self):
            count = unpack('!i', self.file.read(4))[0]
            value = self.file.read(count)
            if _len(value) != count:
                raise StructError("EOF before reading all of bytes type")
            return value

        def read_byte(self):
            return unpack('!b', self.file.read(1))[0]

        def read_bool(self):
            return bool(unpack('!b', self.file.read(1))[0])

        def read_int(self):
            return unpack('!i', self.file.read(4))[0]

        def read_long(self):
            return unpack('!q', self.file.read(8))[0]

        def read_float(self):
            return unpack('!f', self.file.read(4))[0]

        def read_double(self):
            return unpack('!d', self.file.read(8))[0]

        def read_string(self):
            count = unpack('!i', self.file.read(4))[0]
            value = self.file.read(count)
            if _len(value) != count:
                raise StructError("EOF before reading all of string")
            return value

        read_bytestring = read_string

        def read_unicode(self):
            count = unpack('!i', self.file.read(4))[0]
            value = self.file.read(count)
            if _len(value) != count:
                raise StructError("EOF before reading all of string")
            return value.decode(UNICODE_ENCODING, self.unicode_errors)

        def read_vector(self):
            r = self._read
            count = unpack('!i', self.file.read(4))[0]
            try:
                return tuple(r() for i in xrange(count))
            except StopIteration:
                raise StructError("EOF before all vector elements read")

        def read_list(self):
            value = list(self._reads())
            if self.eof:
                raise StructError("EOF before end-of-list marker")
            return value

        def read_map(self):
            r = self._read
            count = unpack('!i', self.file.read(4))[0]
            return dict((r(), r()) for i in xrange(count))

        def read_pickle(self):
            count = unpack('!i', self.file.read(4))[0]
            bytes = self.file.read(count)
            if _len(bytes) != count:
                raise StructError("EOF before reading all of bytes type")
            return loads(bytes)

        def read_marker(self):
            raise StopIteration

        def invalid_typecode(self):
            raise StructError("Invalid type byte: " + str(t))

        TYPECODE_HANDLER_MAP = {
            BYTES: read_bytes,
            BYTE: read_byte,
            BOOL: read_bool,
            INT: read_int,
            LONG: read_long,
            FLOAT: read_float,
            DOUBLE: read_double,
            STRING: read_string,
            VECTOR: read_vector,
            LIST: read_list,
            MAP: read_map,
            PICKLE: read_pickle,
            BYTESTRING: read_bytestring,
            MARKER: read_marker
        }

        def make_handler_table(self):
            return list(Input.TYPECODE_HANDLER_MAP.get(i,
                        Input.invalid_typecode) for i in xrange(256))

        def register(self, typecode, handler):
            self.handler_table[typecode] = handler


    _int, _type = int, type


    def flatten(iterable):
        for i in iterable:
            for j in i:
                yield j


    class Output(object):

        def __init__(self, file, unicode_errors='strict'):
            self.file = file
            self.unicode_errors = unicode_errors
            self.handler_map = self.make_handler_map()

        def __del__(self):
            if not file.closed:
                self.file.flush()

        def _write(self, obj):
            try:
                writefunc = self.handler_map[_type(obj)]
            except KeyError:
                writefunc = Output.write_pickle
            writefunc(self, obj)

        write = _write

        def _writes(self, iterable):
            w = self._write
            for obj in iterable:
                w(obj)

        writes = _writes

        def flush(self):
            self.file.flush()

        def close(self):
            self.file.close()

        def write_bytes(self, bytes):
            self.file.write(pack('!Bi', BYTES, _len(bytes)))
            self.file.write(bytes)

        def write_byte(self, byte):
            self.file.write(pack('!Bb', BYTE, byte))

        def write_bool(self, bool_):
            self.file.write(pack('!Bb', BOOL, _int(bool_)))

        def write_int(self, int_):
            # Python ints are 64-bit
            if -2147483648 <= int_ <= 2147483647:
                self.file.write(pack('!Bi', INT, int_))
            else:
                self.file.write(pack('!Bq', LONG, int_))

        def write_long(self, long_):
            # Python longs are infinite precision
            if -9223372036854775808L <= long_ <= 9223372036854775807L:
                self.file.write(pack('!Bq', LONG, long_))
            else:
                self.write_pickle(long_)

        def write_float(self, float_):
            self.file.write(pack('!Bf', FLOAT, float_))

        def write_double(self, double):
            self.file.write(pack('!Bd', DOUBLE, double))

        def write_string(self, string):
            self.file.write(pack('!Bi', STRING, _len(string)))
            self.file.write(string)

        def write_bytestring(self, string):
            self.file.write(pack('!Bi', BYTESTRING, _len(string)))
            self.file.write(string)

        def write_unicode(self, string):
            string = string.encode(UNICODE_ENCODING, self.unicode_errors)
            self.file.write(pack('!Bi', STRING, _len(string)))
            self.file.write(string)

        def write_vector(self, vector):
            self.file.write(pack('!Bi', VECTOR, _len(vector)))
            self._writes(vector)

        def write_list(self, list_):
            self.file.write(LIST_CODE)
            self._writes(list_)
            self.file.write(MARKER_CODE)

        def write_map(self, map):
            self.file.write(pack('!Bi', MAP, _len(map)))
            self._writes(flatten(map.iteritems()))

        def write_pickle(self, obj):
            bytes = dumps(obj, HIGHEST_PROTOCOL)
            self.file.write(pack('!Bi', PICKLE, _len(bytes)))
            self.file.write(bytes)

        TYPECODE_HANDLER_MAP = {
            BooleanType: write_bool,
            IntType: write_int,                
            LongType: write_long,       
            FloatType: write_double,
            StringType: write_string,
            TupleType: write_vector,
            ListType: write_list,        
            DictType: write_map,
            UnicodeType: write_unicode
        }

        def make_handler_map(self):
            return dict(Output.TYPECODE_HANDLER_MAP)

        def register(self, python_type, handler):
            self.handler_map[python_type] = handler


    class PairedInput(Input):

        def read(self):
            try:
                key = self._read()
            except StopIteration:
                return None
            try:
                value = self._read()
            except StopIteration:
                raise StructError('EOF before second item in pair')
            return key, value

        def reads(self):
            it = self._reads()
            next = it.next
            while 1:
                key = next()
                try:
                    value = next()
                except StopIteration:
                    raise StructError('EOF before second item in pair')
                yield key, value

        __iter__ = reads


    class PairedOutput(Output):

        def write(self, pair):
            self._writes(pair)

        def writes(self, iterable):
            self._writes(flatten(iterable))


    return Input, Output, PairedInput, PairedOutput


Input, Output, PairedInput, PairedOutput = classes()
