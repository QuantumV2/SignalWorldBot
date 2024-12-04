from dataclasses import dataclass

HEADER = 0x53570001

@dataclass
class Vector2:
    x:float = 0.0
    y:float = 0.0


def string_to_tuple(string = "") -> tuple:
	if string:
		new_string = string
		new_string = new_string.erase(0, 1)
		new_string = new_string.erase(new_string.length() - 1, 1)
		array = new_string.split(", ")

		return (int(array[0]), int(array[1]))

	return tuple(0,0)

def create_bitmask(num_bits: int) -> int:
    return (1 << num_bits) - 1

def bits_required(value: int) -> int:
    if value == 0:
        return 1  # Special case: 0 requires 1 bit to represent
    
    # Use logarithm base 2 and ceil to get the minimum number of bits
    import math
    return math.ceil(math.log(abs(value) + 1, 2))

class BitPacker:
    def __init__(self):
        self.data = []
        self.current_byte = 0
        self.bit_position = 0

    def add_bits(self, value: int, num_bits: int) -> None:
        while num_bits > 0:
            bits_to_write = min(8 - self.bit_position, num_bits)
            mask = (1 << bits_to_write) - 1
            shifted_value = (value >> (num_bits - bits_to_write)) & mask
            self.current_byte |= shifted_value << self.bit_position
            self.bit_position += bits_to_write
            num_bits -= bits_to_write
            if self.bit_position == 8:
                self.data.append(self.current_byte)
                self.current_byte = 0
                self.bit_position = 0 

    def get_bytes(self):
        result = bytearray(self.data)
        if self.bit_position > 0:
            result.append(self.current_byte)
        return bytes(result)

class BitReader:
    def __init__(self, bytes_data):
        self.data = bytes_data
        self.byte_index = 0
        self.bit_position = 0

    def read_bits(self, num_bits: int) -> int:
        result = 0
        bits_read = 0
        while bits_read < num_bits:
            if self.byte_index >= len(self.data):
                break
            bits_to_read = min(8 - self.bit_position, num_bits - bits_read)
            mask = (1 << bits_to_read) - 1
            result |= ((self.data[self.byte_index] >> self.bit_position) & mask) << (num_bits - bits_read - bits_to_read)
            self.bit_position += bits_to_read
            bits_read += bits_to_read
            if self.bit_position == 8:
                self.byte_index += 1
                self.bit_position = 0
        return result

    @staticmethod
    def compress(json_data):
        packer = BitPacker()
        cells = json_data['d']
        grid_size = json_data['s']
        
        # Add header (big-endian)
        for i in range(3, -1, -1):
            packer.add_bits((HEADER >> (i * 8)) & 0xFF, 8)

        # Add grid size
        BitReader.encode_varint(packer, grid_size[0])
        BitReader.encode_varint(packer, grid_size[1])
        cells.sort(key=BitReader.sort_cells)

        prev_x = 0
        prev_y = 0
        prev_real_x = 0
        prev_real_y = 0

        for cell in cells:
            x = cell[0][0]
            y = cell[0][1]
            pos_str = cell[1][0]
            powered = cell[1][1]
            rotation = cell[1][2]
            cell_type = cell[1][3]

            # Parse real coordinates
            real_coords = pos_str
            real_x = int(real_coords.x)
            real_y = int(real_coords.y)

            # Delta encode position
            dx = x - prev_x
            dy = y - prev_y
            BitReader.encode_varint(packer, dx)
            BitReader.encode_varint(packer, dy)

            # Delta encode real position
            real_dx = real_x - prev_real_x
            real_dy = real_y - prev_real_y
            BitReader.encode_varint(packer, real_dx)
            BitReader.encode_varint(packer, real_dy)

            # Encode other properties
            packer.add_bits(powered & 0b00001111, 4)
            packer.add_bits(rotation // 90 & 0b00000011, 2)
            packer.add_bits(0, 2)
            BitReader.encode_varint(packer, cell_type)

            prev_x = x
            prev_y = y
            prev_real_x = real_x
            prev_real_y = real_y

        return packer.get_bytes()

    @staticmethod
    def decompress(compressed_data):
        reader = BitReader(compressed_data)
        result = {"d": [], "s": []}

        # Check header (big-endian)
        header = (reader.read_bits(8) << 24) | (reader.read_bits(8) << 16) | (reader.read_bits(8) << 8) | reader.read_bits(8)
        if header != HEADER:
            print("Invalid header")
            return result

        # Read grid size
        result["s"] = [decode_varint(reader), decode_varint(reader)]

        prev_x = 0
        prev_y = 0
        prev_real_x = 0
        prev_real_y = 0

        while reader.byte_index < len(compressed_data) or reader.bit_position != 0:
            # Delta decode position
            dx = decode_varint(reader)
            dy = decode_varint(reader)
            x = prev_x + dx
            y = prev_y + dy
            
            # Delta decode real position
            real_dx = decode_varint(reader)
            real_dy = decode_varint(reader)
            real_x = prev_real_x + real_dx
            real_y = prev_real_y + real_dy

            # Decode other properties
            powered = reader.read_bits(4)
            rotation = reader.read_bits(2) * 90
            reader.read_bits(2)
            cell_type = decode_varint(reader)

            # Construct cell data
            cell = [
                [x, y],
                [Vector2(real_x, real_y), powered, rotation, cell_type]
            ]
            result["d"].append(cell)

            prev_x = x
            prev_y = y
            prev_real_x = real_x
            prev_real_y = real_y

        return result

def encode_varint(packer: BitPacker, value: int) -> None:
    unsigned_value = (value << 1) ^ (value >> 31)  # zigzag encoding
    while unsigned_value >= 0x80:
        packer.add_bits((unsigned_value & 0x7f) | 0x80, 8)
        unsigned_value >>= 7
    packer.add_bits(unsigned_value, 8)


def decode_varint(reader: BitReader) -> int:
    value = 0
    shift = 0
    while True:
        byte = reader.read_bits(8)
        value |= (byte & 0x7f) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return (value >> 1) ^ -(value & 1)  # zigzag decoding

def sort_cells(a, b):
    if a[0][0] != b[0][0]:
        return a[0][0] < b[0][0]
    return a[0][1] < b[0][1]